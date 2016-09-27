import logging

from django.core.management.base import LabelCommand

from v6score.management.commands import init_logging
from v6score.models import Website, Measurement

logger = logging.getLogger()


class Command(LabelCommand):
    help = 'Test the given domain name and compare IPv4-only vs IPv6-only vs NAT64 results'
    label = 'domain'
    missing_args_message = "Enter at least one domain name."

    def handle(self, *labels, **options):
        init_logging(logger, int(options['verbosity']))
        super(Command, self).handle(*labels, **options)

    def handle_label(self, label, **options):
        # First find or create the website
        website = Website.objects.get_or_create(hostname=label.strip())[0]

        # Build the test results
        results = Measurement(website=website, manual=True)

        results.run_test()
