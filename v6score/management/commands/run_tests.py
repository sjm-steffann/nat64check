import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.utils import timezone

from v6score.management.commands import init_logging
from v6score.models import Measurement

logger = logging.getLogger()


class Command(BaseCommand):
    help = "Run tests that haven't been processed yet"

    def handle(self, **options):
        init_logging(logger, int(options['verbosity']))

        stopping = []

        def stop_me(sig_num, stack):
            logger.critical("Interrupt received, please wait while we finish the current test")
            stopping.append(True)

        signal.signal(signal.SIGINT, stop_me)

        while not stopping:
            # Take ownership of the next test
            measurement = None
            while True:
                try:
                    with transaction.atomic():
                        measurement = Measurement.objects \
                            .select_for_update() \
                            .filter(started=None) \
                            .order_by('requested') \
                            .first()

                        if measurement:
                            # Setting started will let other scripts know this one is being handled
                            measurement.started = timezone.now()
                            measurement.save()
                except TransactionManagementError:
                    pass

                break

            # Run test
            if stopping:
                break

            if measurement:
                logging.info("Running {}".format(measurement))
                result = measurement.run_test()
                if result & 5 != 0:
                    logging.warning("Dubious result, re-scheduling test")
                    new_measurement = Measurement(website=measurement.website)
                    new_measurement.save()

            else:
                logger.debug("Nothing to process, sleeping")
                time.sleep(5)
