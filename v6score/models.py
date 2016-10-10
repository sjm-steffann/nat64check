import base64
import datetime
import io
import json
import logging
import os
import re
import signal
import tempfile
import time
import warnings
from collections import OrderedDict
from subprocess import Popen, PIPE, TimeoutExpired

import skimage.io
import yaml
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from psycopg2.extras import register_default_json, register_default_jsonb
from skimage.measure import compare_ssim

from nat64check import settings

logger = logging.getLogger(__name__)


def is_valid_hostname(hostname):
    if not (0 < len(hostname) < 255):
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    allowed = re.compile("^(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    parts = hostname.split(".")
    if len(parts) < 2:
        return False
    return all(allowed.match(x) for x in parts)


def validate_hostname(hostname):
    if not is_valid_hostname(hostname):
        raise ValidationError("Invalid hostname")


class Website(models.Model):
    hostname = models.CharField(max_length=128, unique=True, validators=[validate_hostname])
    hash_param = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.hostname

    class Meta:
        ordering = ('hostname',)


def my_basedir(instance, filename):
    return 'capture/{}/{}/{}'.format(instance.website.hostname,
                                     datetime.datetime.now().strftime('%Y-%m-%d/%H-%M'),
                                     filename)


def ignore_signals():
    # Ignore the SIGINT signal by setting the handler to the standard
    # signal handler SIG_IGN.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class Measurement(models.Model):
    website = models.ForeignKey(Website)

    manual = models.BooleanField(default=False)
    retry_for = models.ForeignKey('self', blank=True, null=True)

    requested = models.DateTimeField()
    started = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)

    v4only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    v6only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    nat64_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)

    v4only_data = JSONField(blank=True, null=True)
    v4only_debug = models.TextField(blank=True)

    v6only_data = JSONField(blank=True, null=True)
    v6only_debug = models.TextField(blank=True)

    nat64_data = JSONField(blank=True, null=True)
    nat64_debug = models.TextField(blank=True)

    v6only_image_score = models.FloatField(blank=True, null=True)
    nat64_image_score = models.FloatField(blank=True, null=True)

    v6only_resource_score = models.FloatField(blank=True, null=True)
    nat64_resource_score = models.FloatField(blank=True, null=True)

    def __str__(self):
        prefix = 'Manual ' if self.manual else ''
        prefix += 'Retry ' if self.retry_for else ''

        if self.finished:
            return prefix + 'Test #{}: {} finished at {}'.format(self.pk, self.website.hostname, self.finished)
        elif self.started:
            return prefix + 'Test #{}: {} started at {}'.format(self.pk, self.website.hostname, self.started)
        else:
            return prefix + 'Test #{}: {} requested at {}'.format(self.pk, self.website.hostname, self.requested)

    def get_absolute_url(self):
        return reverse('measurement', args=(self.pk,))

    @property
    def v6only_score(self):
        if self.v6only_resource_score is None:
            return self.v6only_image_score

        return (self.v6only_image_score + self.v6only_resource_score) / 2

    @property
    def nat64_score(self):
        if self.nat64_resource_score is None:
            return self.nat64_image_score

        return (self.nat64_image_score + self.nat64_resource_score) / 2

    @property
    def v4only_resources(self):
        ok = 0
        error = 0
        for resource in self.v4only_data.get('resources', {}).values():
            if resource.get('stage') == 'end' and not resource.get('error', True):
                ok += 1
            else:
                error += 1

        return ok, error

    @property
    def v6only_resources(self):
        ok = 0
        error = 0
        for resource in self.v6only_data.get('resources', {}).values():
            if resource.get('stage') == 'end' and not resource.get('error', True):
                ok += 1
            else:
                error += 1

        return ok, error

    @property
    def nat64_resources(self):
        ok = 0
        error = 0
        for resource in self.nat64_data.get('resources', {}).values():
            if resource.get('stage') == 'end' and not resource.get('error', True):
                ok += 1
            else:
                error += 1

        return ok, error

    def run_test(self):
        url = 'http://{}/'.format(self.website.hostname)
        if self.website.hash_param:
            url += '#' + self.website.hash_param

        if self.finished:
            logger.error("{}: test already finished".format(url))
            return

        # Update started
        self.started = timezone.now()

        # Common stuff
        script = os.path.realpath(os.path.join(
            os.path.dirname(__file__),
            'render_page.js'
        ))
        common_options = [
            'phantomjs',
            '--debug=true',
            '--ignore-ssl-errors=true',
            # This is the solution for upcoming versions of PhantomJS:
            # '--local-storage-quota=-1',
            # '--offline-storage-quota=-1',
            # For now we create a new temp path for each run (see below)
        ]

        with tempfile.TemporaryDirectory() as run_temp:
            # Make a few subdirectories
            v4only_temp = os.path.join(run_temp, 'v4only')
            v6only_temp = os.path.join(run_temp, 'v6only')
            nat64_temp = os.path.join(run_temp, 'nat64')

            os.makedirs(v4only_temp)
            os.makedirs(v6only_temp)
            os.makedirs(nat64_temp)

            # Do the v4-only, v6-only and the NAT64 request in parallel
            v4only_process = Popen(
                common_options
                + ['--local-storage-path=' + v4only_temp,
                   '--offline-storage-path=' + v4only_temp,
                   '--proxy=' + settings.V4PROXY]
                + [script, url],
                stdout=PIPE, stderr=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(v4only_process.args)))

            v6only_process = Popen(
                common_options
                + ['--local-storage-path=' + v6only_temp,
                   '--offline-storage-path=' + v6only_temp,
                   '--proxy=' + settings.V6PROXY]
                + [script, url],
                stdout=PIPE, stderr=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(v6only_process.args)))

            nat64_process = Popen(
                common_options
                + ['--local-storage-path=' + nat64_temp,
                   '--offline-storage-path=' + nat64_temp,
                   '--proxy=' + settings.NAT64PROXY]
                + [script, url],
                stdout=PIPE, stderr=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(nat64_process.args)))

            # Placeholders
            v4only_img = None
            v4only_img_bytes = None
            v6only_img = None
            v6only_img_bytes = None
            nat64_img = None
            nat64_img_bytes = None

            self.v4only_data = {}
            self.v6only_data = {}
            self.nat64_data = {}

            # Wait for tests to finish
            start_time = time.time()
            full_timeout = 30
            timeout = full_timeout
            try:
                v4only_json, v4only_debug = v4only_process.communicate(timeout=timeout)
                self.v4only_data = json.loads(
                    v4only_json.decode('utf-8'),
                    object_pairs_hook=OrderedDict
                ) if v4only_json else {}
                self.v4only_debug = v4only_debug.decode('utf-8')
                if 'image' in self.v4only_data:
                    if self.v4only_data['image']:
                        v4only_img_bytes = base64.decodebytes(self.v4only_data['image'].encode('ascii'))
                        # noinspection PyTypeChecker
                        v4only_img = skimage.io.imread(io.BytesIO(v4only_img_bytes))
                    del self.v4only_data['image']

            except TimeoutExpired:
                logger.error("{}: IPv4-only load timed out".format(url))
                v4only_process.kill()

            timeout = full_timeout - (time.time() - start_time)
            try:
                v6only_json, v6only_debug = v6only_process.communicate(timeout=timeout)
                self.v6only_data = json.loads(
                    v6only_json.decode('utf-8'),
                    object_pairs_hook=OrderedDict
                ) if v6only_json else {}
                self.v6only_debug = v6only_debug.decode('utf-8')
                if 'image' in self.v6only_data:
                    if self.v6only_data['image']:
                        v6only_img_bytes = base64.decodebytes(self.v6only_data['image'].encode('ascii'))
                        # noinspection PyTypeChecker
                        v6only_img = skimage.io.imread(io.BytesIO(v6only_img_bytes))
                    del self.v6only_data['image']
            except TimeoutExpired:
                logger.error("{}: IPv6-only load timed out".format(url))
                v6only_process.kill()

            timeout = full_timeout - (time.time() - start_time)
            try:
                nat64_json, nat64_debug = nat64_process.communicate(timeout=timeout)
                self.nat64_data = json.loads(
                    nat64_json.decode('utf-8'),
                    object_pairs_hook=OrderedDict
                ) if nat64_json else {}
                self.nat64_debug = nat64_debug.decode('utf-8')
                if 'image' in self.nat64_data:
                    if self.nat64_data['image']:
                        nat64_img_bytes = base64.decodebytes(self.nat64_data['image'].encode('ascii'))
                        # noinspection PyTypeChecker
                        nat64_img = skimage.io.imread(io.BytesIO(nat64_img_bytes))
                    del self.nat64_data['image']
            except TimeoutExpired:
                logger.error("{}: NAT64 load timed out".format(url))
                nat64_process.kill()

        # Calculate score based on resources
        v4only_resources_ok = self.v4only_resources[0]
        if v4only_resources_ok > 0:
            self.v6only_resource_score = min(self.v6only_resources[0] / v4only_resources_ok, 1)
            logger.info("{}: IPv6-only Resource Score = {:0.2f}".format(url, self.v6only_resource_score))

            self.nat64_resource_score = min(self.nat64_resources[0] / v4only_resources_ok, 1)
            logger.info("{}: NAT64 Resource Score = {:0.2f}".format(url, self.nat64_resource_score))
        else:
            logger.error("{}: did not load over IPv4-only, unable to perform resource test".format(url))

        return_value = 0
        if v4only_img_bytes:
            # Store the image
            self.v4only_image.save('v4.png', ContentFile(v4only_img_bytes), save=False)
        else:
            return_value |= 1

        if v6only_img_bytes:
            # Store the image
            self.v6only_image.save('v6.png', ContentFile(v6only_img_bytes), save=False)
        else:
            return_value |= 2

        if nat64_img_bytes:
            # Store the image
            self.nat64_image.save('nat64.png', ContentFile(nat64_img_bytes), save=False)
        else:
            return_value |= 4

        if v4only_img is not None:
            logger.debug("{}: Loading IPv4-only screenshot".format(url))

            if v6only_img is not None:
                logger.debug("{}: Loading IPv6-only screenshot".format(url))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    self.v6only_image_score = compare_ssim(v4only_img, v6only_img, multichannel=True)
                    logger.info("{}: IPv6-only Image Score = {:0.2f}".format(url, self.v6only_image_score))
            else:
                logger.warning("{}: did not load over IPv6-only, 0 score".format(url))
                self.v6only_image_score = 0.0

            if nat64_img is not None:
                logger.debug("{}: Loading NAT64 screenshot".format(url))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    self.nat64_image_score = compare_ssim(v4only_img, nat64_img, multichannel=True)
                    logger.info("{}: NAT64 Image Score = {:0.2f}".format(url, self.nat64_image_score))
            else:
                logger.warning("{}: did not load over NAT64, 0 score".format(url))
                self.nat64_image_score = 0.0

        else:
            logger.error("{}: did not load over IPv4-only, unable to perform image test".format(url))

        self.finished = timezone.now()
        self.save()

        return return_value


# Proper representation with OrderedDict
register_default_json(globally=True, loads=lambda s: json.loads(s, object_pairs_hook=OrderedDict))
register_default_jsonb(globally=True, loads=lambda s: json.loads(s, object_pairs_hook=OrderedDict))

yaml.add_representer(OrderedDict,
                     lambda self, data: self.represent_mapping('tag:yaml.org,2002:map', data.items()))
