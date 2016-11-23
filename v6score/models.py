import base64
import datetime
import io
import json
import logging
import os
import re
import signal
import subprocess
import time
import warnings
from collections import OrderedDict
from datetime import timedelta
from ipaddress import ip_address, IPv4Address, IPv6Address
from typing import List, Iterable, Union
from urllib.parse import urlparse, urlunparse

import skimage.io
import yaml
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.fields.array import ArrayField
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from psycopg2.extras import register_default_json, register_default_jsonb
from skimage.measure import compare_ssim

from nat64check import settings

logger = logging.getLogger(__name__)


def get_addresses(hostname) -> List[Union[IPv4Address, IPv6Address]]:
    # Get DNS info
    try:
        a_records = subprocess.check_output(args=['dig', '+short', 'a', hostname],
                                            stderr=subprocess.DEVNULL)
        aaaa_records = subprocess.check_output(args=['dig', '+short', 'aaaa', hostname],
                                               stderr=subprocess.DEVNULL)
        dns_records = a_records + aaaa_records

        dns_results = []
        for line in dns_records.decode('utf-8').strip().split():
            try:
                dns_results.append(str(ip_address(line)))
            except ValueError:
                pass
    except subprocess.CalledProcessError:
        dns_results = []

    return dns_results


def start_ping(args: Iterable) -> subprocess.Popen:
    return subprocess.Popen(
        args=args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        preexec_fn=ignore_signals,
        cwd='/tmp'
    )


def parse_ping(ping_output: bytes) -> List:
    ping_latencies = {nr: -1 for nr in range(1, 6)}
    for line in ping_output.decode('utf-8').split('\n'):
        nr_match = re.search("icmp_seq=(\d+) ", line)
        if nr_match:
            nr = int(nr_match.group(1))
        else:
            continue

        time_match = re.search("time=(\d+(\.(\d+))?) ms", line)
        if time_match:
            ping_latencies[nr] = float(time_match.group(1))
        else:
            if 'filtered' in line:
                ping_latencies[nr] = -2

    # Some ping implementations start counting at 0
    # If so, nr goes from 0-4 instead of 1-5
    if 0 in ping_latencies:
        del ping_latencies[5]

    return [ping_latencies[key] for key in sorted(ping_latencies.keys())]


def my_basedir(instance, filename):
    return 'capture/{}/{}/{}'.format(instance.hostname,
                                     datetime.datetime.now().strftime('%Y-%m-%d/%H-%M'),
                                     filename)


def ignore_signals():
    # Ignore the SIGINT signal by setting the handler to the standard
    # signal handler SIG_IGN.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class MeasurementManager(models.Manager):
    @staticmethod
    def get_measurement_for_url(url, force_new=False):
        measurement = Measurement.objects.filter(url=url, started=None).order_by('requested').first()
        if measurement:
            if not measurement.manual:
                # Mark as manual
                measurement.manual = True

            if not measurement.started or measurement.started < (timezone.now() - timedelta(minutes=5)):
                # Measurement not started, or measurement started more than 5 minutes ago (broken)
                measurement.requested = timezone.now()
                measurement.started = None
                measurement.save()
        else:
            recent = timezone.now() - timedelta(minutes=10)
            measurement = Measurement.objects.filter(url=url, finished__gt=recent).order_by('-finished').first()
            if not measurement or force_new:
                measurement = Measurement(url=url, requested=timezone.now(), manual=True)
                measurement.save()

        return measurement


class Measurement(models.Model):
    url = models.URLField(db_index=True)

    manual = models.BooleanField(default=False, db_index=True)
    retry_for = models.ForeignKey('self', blank=True, null=True, db_index=True)

    requested = models.DateTimeField(db_index=True)
    started = models.DateTimeField(blank=True, null=True, db_index=True)
    finished = models.DateTimeField(blank=True, null=True, db_index=True)
    latest = models.BooleanField(default=False, db_index=True)

    dns_results = ArrayField(models.GenericIPAddressField(), blank=True, default=list)

    ping4_latencies = ArrayField(models.FloatField(), blank=True, default=list)
    ping4_1500_latencies = ArrayField(models.FloatField(), blank=True, default=list)
    ping4_2000_latencies = ArrayField(models.FloatField(), blank=True, default=list)
    ping6_latencies = ArrayField(models.FloatField(), blank=True, default=list)
    ping6_1500_latencies = ArrayField(models.FloatField(), blank=True, default=list)
    ping6_2000_latencies = ArrayField(models.FloatField(), blank=True, default=list)

    v4only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    v6only_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)
    nat64_image = models.ImageField(upload_to=my_basedir, blank=True, null=True)

    v4only_data = JSONField(blank=True, null=True)
    v4only_debug = models.TextField(blank=True)

    v6only_data = JSONField(blank=True, null=True)
    v6only_debug = models.TextField(blank=True)

    nat64_data = JSONField(blank=True, null=True)
    nat64_debug = models.TextField(blank=True)

    v6only_image_score = models.FloatField(blank=True, null=True, db_index=True)
    nat64_image_score = models.FloatField(blank=True, null=True, db_index=True)

    v6only_resource_score = models.FloatField(blank=True, null=True, db_index=True)
    nat64_resource_score = models.FloatField(blank=True, null=True, db_index=True)

    objects = MeasurementManager()

    class Meta:
        index_together = [
            ['v6only_image_score', 'nat64_image_score'],
            ['v6only_resource_score', 'nat64_resource_score'],
        ]

    def __str__(self):
        prefix = 'Manual ' if self.manual else ''
        prefix += 'Retry ' if self.retry_for else ''

        if self.finished:
            return prefix + 'Test #{}: {} finished at {}'.format(self.pk, self.url, self.finished)
        elif self.started:
            return prefix + 'Test #{}: {} started at {}'.format(self.pk, self.url, self.started)
        else:
            return prefix + 'Test #{}: {} requested at {}'.format(self.pk, self.url, self.requested)

    def get_absolute_url(self):
        return reverse('measurement', args=(self.pk,))

    @property
    def hostname(self):
        url_parts = urlparse(self.url, scheme='http')
        return url_parts.netloc

    @hostname.setter
    def hostname(self, new_hostname):
        scheme, netloc, path, params, query, fragment = urlparse(self.url, scheme='http')
        netloc = new_hostname
        self.url = urlunparse((scheme, netloc, path, params, query, fragment))

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

    def run_dns_tests(self):
        if self.finished:
            logger.error("{}: test already finished".format(self.url))
            return

        dns_results = get_addresses(self.hostname)

        # If no records and no www in URL then try again with www
        if not dns_results and not self.hostname.startswith('www.'):
            try_hostname = 'www.' + self.hostname
            dns_results = get_addresses(try_hostname)
            if not dns_results:
                logger.error("Hostname {} doesn't resolve".format(self.hostname))
            else:
                logger.warning("Hostname {} didn't resolve, using {}".format(self.hostname, try_hostname))
                self.hostname = try_hostname

        for address in dns_results:
            logger.info("Found address for {}: {}".format(self.hostname, address))

        self.dns_results = dns_results
        self.save()

    def run_ping_tests(self):
        if self.finished:
            logger.error("{}: test already finished".format(self.url))
            return

        # Ping
        ping4_process = start_ping(['ping', '-c5', '-n', self.hostname])
        ping4_1500_process = start_ping(['ping', '-c5', '-n', '-s1472', '-Mwant', self.hostname])
        ping4_2000_process = start_ping(['ping', '-c5', '-n', '-s1972', '-Mwant', self.hostname])
        ping6_process = start_ping(['ping6', '-c5', '-n', self.hostname])
        ping6_1500_process = start_ping(['ping6', '-c5', '-n', '-s1452', '-Mwant', self.hostname])
        ping6_2000_process = start_ping(['ping6', '-c5', '-n', '-s1952', '-Mwant', self.hostname])

        self.ping4_latencies = parse_ping(ping4_process.communicate()[0])
        logger.info("Ping IPv4 results: {}".format(self.ping4_latencies))

        self.ping4_1500_latencies = parse_ping(ping4_1500_process.communicate()[0])
        logger.info("Ping IPv4 (1500) results: {}".format(self.ping4_1500_latencies))

        self.ping4_2000_latencies = parse_ping(ping4_2000_process.communicate()[0])
        logger.info("Ping IPv4 (2000) results: {}".format(self.ping4_2000_latencies))

        self.ping6_latencies = parse_ping(ping6_process.communicate()[0])
        logger.info("Ping IPv6 results: {}".format(self.ping6_latencies))

        self.ping6_1500_latencies = parse_ping(ping6_1500_process.communicate()[0])
        logger.info("Ping IPv6 (1500) results: {}".format(self.ping6_1500_latencies))

        self.ping6_2000_latencies = parse_ping(ping6_2000_process.communicate()[0])
        logger.info("Ping IPv6 (2000) results: {}".format(self.ping6_2000_latencies))

        self.save()

    def run_browser_tests(self):
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

        # Do the v4-only, v6-only and the NAT64 request in parallel
        v4only_process = subprocess.Popen(
            common_options
            + ['--local-storage-path=/dev/null',
               '--offline-storage-path=/dev/null',
               '--proxy=' + settings.V4PROXY]
            + [script, self.url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=ignore_signals,
            cwd='/tmp'
        )
        logger.debug("Running {}".format(' '.join(v4only_process.args)))

        v6only_process = subprocess.Popen(
            common_options
            + ['--local-storage-path=/dev/null',
               '--offline-storage-path=/dev/null',
               '--proxy=' + settings.V6PROXY]
            + [script, self.url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=ignore_signals,
            cwd='/tmp'
        )
        logger.debug("Running {}".format(' '.join(v6only_process.args)))

        nat64_process = subprocess.Popen(
            common_options
            + ['--local-storage-path=/dev/null',
               '--offline-storage-path=/dev/null',
               '--proxy=' + settings.NAT64PROXY]
            + [script, self.url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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

        except subprocess.TimeoutExpired:
            logger.error("{}: IPv4-only load timed out".format(self.url))
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
        except subprocess.TimeoutExpired:
            logger.error("{}: IPv6-only load timed out".format(self.url))
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
        except subprocess.TimeoutExpired:
            logger.error("{}: NAT64 load timed out".format(self.url))
            nat64_process.kill()

        # Calculate score based on resources
        v4only_resources_ok = self.v4only_resources[0]
        if v4only_resources_ok > 0:
            self.v6only_resource_score = min(self.v6only_resources[0] / v4only_resources_ok, 1)
            logger.info("{}: IPv6-only Resource Score = {:0.2f}".format(self.url, self.v6only_resource_score))

            self.nat64_resource_score = min(self.nat64_resources[0] / v4only_resources_ok, 1)
            logger.info("{}: NAT64 Resource Score = {:0.2f}".format(self.url, self.nat64_resource_score))
        else:
            logger.error("{}: did not load over IPv4-only, unable to perform resource test".format(self.url))

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
            logger.debug("{}: Loading IPv4-only screenshot".format(self.url))

            if v6only_img is not None:
                logger.debug("{}: Loading IPv6-only screenshot".format(self.url))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    self.v6only_image_score = compare_ssim(v4only_img, v6only_img, multichannel=True)
                    logger.info("{}: IPv6-only Image Score = {:0.2f}".format(self.url, self.v6only_image_score))
            else:
                logger.warning("{}: did not load over IPv6-only, 0 score".format(self.url))
                self.v6only_image_score = 0.0

            if nat64_img is not None:
                logger.debug("{}: Loading NAT64 screenshot".format(self.url))

                # Suppress stupid warnings
                with warnings.catch_warnings(record=True):
                    self.nat64_image_score = compare_ssim(v4only_img, nat64_img, multichannel=True)
                    logger.info("{}: NAT64 Image Score = {:0.2f}".format(self.url, self.nat64_image_score))
            else:
                logger.warning("{}: did not load over NAT64, 0 score".format(self.url))
                self.nat64_image_score = 0.0

        else:
            logger.error("{}: did not load over IPv4-only, unable to perform image test".format(self.url))

        self.save()

        return return_value

    def run_test(self):
        if self.finished:
            logger.error("{}: test already finished".format(self.url))
            return

        # Update started
        self.started = timezone.now()

        # Run tests
        self.run_dns_tests()

        # Abort quickly if no DNS
        if not self.dns_results:
            logger.error("Aborting test, no addresses found")
            return_value = 8
        else:
            self.run_ping_tests()
            return_value = self.run_browser_tests()

        # Set all other "latest" flags to false
        Measurement.objects.filter(url=self.url, latest=True).update(latest=False)

        self.latest = True
        self.finished = timezone.now()
        self.save()

        return return_value


# Proper representation with OrderedDict
register_default_json(globally=True, loads=lambda s: json.loads(s, object_pairs_hook=OrderedDict))
register_default_jsonb(globally=True, loads=lambda s: json.loads(s, object_pairs_hook=OrderedDict))

yaml.add_representer(OrderedDict,
                     lambda self, data: self.represent_mapping('tag:yaml.org,2002:map', data.items()))
