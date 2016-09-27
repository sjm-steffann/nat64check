import logging
from datetime import timedelta

from django.core.management.base import LabelCommand
from django.utils import timezone

from v6score.management.commands import init_logging
from v6score.models import Website, Measurement, is_valid_hostname

logger = logging.getLogger()


class Command(LabelCommand):
    help = 'Add the given hostname to the test queue'
    label = 'hostname'
    missing_args_message = "Enter at least one hostname."

    def handle(self, *labels, **options):
        init_logging(logger, int(options['verbosity']))
        super(Command, self).handle(*labels, **options)

    def handle_label(self, label, **options):
        hostname = label.strip()
        if not is_valid_hostname(hostname):
            logger.error("{} is not a valid hostname".format(hostname))
            return

        # First find or create the website
        website = Website.objects.get_or_create(hostname=hostname)[0]
        measurement = website.measurement_set.filter(finished=None).order_by('requested').first()
        if measurement:
            logger.warning("{} already has an open request".format(hostname))
        else:
            recent = timezone.now() - timedelta(minutes=10)
            measurement = website.measurement_set.filter(finished__gt=recent).order_by('-finished').first()
            if measurement:
                logger.warning("{} has already been tested recently".format(hostname))
            else:
                measurement = Measurement(website=website)
                measurement.save()
                logger.info("{} request added".format(hostname))
