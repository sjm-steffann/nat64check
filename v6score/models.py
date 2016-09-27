import datetime
import io
import logging
import os
import re
import signal
import tempfile
import warnings
from subprocess import Popen, PIPE, TimeoutExpired

import skimage.io
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
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
    requested = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(blank=True, null=True)
    finished = models.DateTimeField(blank=True, null=True)

    v4only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    v6only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    nat64_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)

    v6only_score = models.FloatField(blank=True, null=True)
    nat64_score = models.FloatField(blank=True, null=True)

    def __str__(self):
        if self.finished:
            return 'Test #{}: {} finished at {}'.format(self.pk, self.website.hostname, self.finished)
        elif self.started:
            return 'Test #{}: {} started at {}'.format(self.pk, self.website.hostname, self.started)
        else:
            return 'Test #{}: {} requested at {}'.format(self.pk, self.website.hostname, self.requested)

    def get_absolute_url(self):
        return reverse('measurement', args=(self.pk,))

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
                + ['--local-storage-path=' + v4only_temp]
                + [script, url, settings.V4PROXY_HOST, str(settings.V4PROXY_PORT)],
                stdout=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(v4only_process.args)))

            v6only_process = Popen(
                common_options
                + ['--local-storage-path=' + v6only_temp]
                + [script, url, settings.V6PROXY_HOST, str(settings.V6PROXY_PORT)],
                stdout=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(v6only_process.args)))

            nat64_process = Popen(
                common_options
                + ['--local-storage-path=' + nat64_temp]
                + [script, url, settings.NAT64PROXY_HOST, str(settings.NAT64PROXY_PORT)],
                stdout=PIPE,
                preexec_fn=ignore_signals,
                cwd='/tmp'
            )
            logger.debug("Running {}".format(' '.join(nat64_process.args)))

            # Wait for tests to finish
            timeout = 30
            try:
                v4only_out = v4only_process.communicate(timeout=timeout)[0]
            except TimeoutExpired:
                logger.error("{}: IPv4-only load timed out".format(url))
                v4only_process.kill()
                v4only_out = None

            if v4only_out:
                try:
                    v6only_out = v6only_process.communicate(timeout=timeout)[0]
                except TimeoutExpired:
                    logger.error("{}: IPv6-only load timed out".format(url))
                    v6only_process.kill()
                    v6only_out = None

                try:
                    nat64_out = nat64_process.communicate(timeout=timeout)[0]
                except TimeoutExpired:
                    logger.error("{}: NAT64 load timed out".format(url))
                    nat64_process.kill()
                    nat64_out = None
            else:
                v6only_process.kill()
                v6only_out = None

                nat64_process.kill()
                nat64_out = None

        v4only_ok = v4only_out and v4only_process.returncode == 0
        return_value = 0
        if v4only_ok:
            # Store the image
            self.v4only_image.save('v4.png', ContentFile(v4only_out), save=False)
        else:
            return_value |= 1

        v6only_ok = v6only_out and v6only_process.returncode == 0
        if v6only_ok:
            # Store the image
            self.v6only_image.save('v6.png', ContentFile(v6only_out), save=False)
        else:
            return_value |= 2

        nat64_ok = nat64_out and nat64_process.returncode == 0
        if nat64_ok:
            # Store the image
            self.nat64_image.save('nat64.png', ContentFile(nat64_out), save=False)
        else:
            return_value |= 4

        if v4only_ok:
            logger.debug("{}: Loading IPv4-only screenshot".format(url))
            # noinspection PyTypeChecker
            v4only_img = skimage.io.imread(io.BytesIO(v4only_out))

            if v6only_ok:
                logger.debug("{}: Loading IPv6-only screenshot".format(url))
                # noinspection PyTypeChecker
                v6only_img = skimage.io.imread(io.BytesIO(v6only_out))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    score = compare_ssim(v4only_img, v6only_img, multichannel=True)
                    self.v6only_score = score
                    logger.info("{}: IPv6-only Score = {:0.2f}".format(url, score))
            else:
                logger.warning("{}: did not load over IPv6-only, 0 score".format(url))
                self.v6only_score = 0.0

            if nat64_ok:
                logger.debug("{}: Loading NAT64 screenshot".format(url))
                # noinspection PyTypeChecker
                nat64_img = skimage.io.imread(io.BytesIO(nat64_out))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    score = compare_ssim(v4only_img, nat64_img, multichannel=True)
                    self.nat64_score = score
                    logger.info("{}: NAT64 Score = {:0.2f}".format(url, score))
            else:
                logger.warning("{}: did not load over NAT64, 0 score".format(url))
                self.nat64_score = 0.0

        else:
            logger.error("{}: did not load over IPv4-only, unable to perform test".format(url))

        self.finished = timezone.now()
        self.save()

        return return_value
