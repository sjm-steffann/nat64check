import logging

from django.core.management.base import LabelCommand
from django.utils import timezone

from v6score.forms import URLForm
from v6score.management.commands import init_logging
from v6score.models import Measurement

logger = logging.getLogger()


class Command(LabelCommand):
    help = 'Test the given domain name and compare IPv4-only vs IPv6-only vs NAT64 results'
    label = 'domain'
    missing_args_message = "Enter at least one domain name."

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

        results = Measurement(url=url, requested=timezone.now(), manual=True)
        results.run_test()
