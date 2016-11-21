import logging
from datetime import timedelta

from django.core.management.base import LabelCommand
from django.utils import timezone

from v6score.forms import URLForm
from v6score.management.commands import init_logging
from v6score.models import Measurement

logger = logging.getLogger()


class Command(LabelCommand):
    help = 'Add the given URL to the test queue'
    label = 'hostname'
    missing_args_message = "Enter at least one URL."

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
        url_form = URLForm({
            'url': label
        })
        if not url_form.is_valid():
            logger.critical("Invalid URL: {}".format(label))
            return

        # Get the cleaned URL from the form
        url = url_form.cleaned_data['url']

        measurement = Measurement.objects.filter(url=url, finished=None).order_by('requested').first()
        if measurement:
            if options['manual'] and not measurement.manual:
                measurement.manual = True

            measurement.requested = timezone.now()
            measurement.save()
            logger.info("{} existing request marked as manual".format(url))
        else:
            recent = timezone.now() - timedelta(minutes=5)
            measurement = Measurement.objects.filter(url=url, finished__gt=recent).order_by('-finished').first()
            if not options['manual'] and measurement:
                logger.warning("{} has already been tested recently".format(url))
            else:
                measurement = Measurement(url=url, requested=timezone.now(), manual=options['manual'])
                measurement.save()
                logger.info("{} request added".format(url))
