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

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--manual',
            action='store_true',
            dest='manual',
            default=False,
            help='Mark this request as manual',
        )

        super().add_arguments(parser)

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
            if options['manual'] and not measurement.manual:
                measurement.manual = True
                measurement.save()
                logger.info("{} existing request marked as manual".format(hostname))
            else:
                logger.warning("{} already has an open manual request".format(hostname))
        else:
            recent = timezone.now() - timedelta(minutes=10)
            measurement = website.measurement_set.filter(finished__gt=recent).order_by('-finished').first()
            if not options['manual'] and measurement:
                logger.warning("{} has already been tested recently".format(hostname))
            else:
                measurement = Measurement(website=website, manual=options['manual'])
                measurement.save()
                logger.info("{} request added".format(hostname))
