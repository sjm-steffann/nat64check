import logging
import os
from logging import Filter, getLevelName

from django.conf import settings
from django.core.management.base import BaseCommand
from paramiko.client import AutoAddPolicy, SSHClient

from v6score.management.commands import init_logging

logger = logging.getLogger()


class ParamikoLogFilter(Filter):
    def filter(self, record):
        if 'host key' in record.getMessage():
            record.levelno = logging.INFO
            record.levelname = getLevelName(logging.INFO)

        return record.levelno >= logging.INFO


class Command(BaseCommand):
    help = 'Make sure all the host keys for workers are known'

    def handle(self, *labels, **options):
        init_logging(logger, 3)

        try:
            # Make sure the directory and the file exist
            dirname = os.path.dirname(settings.SSH_KNOWN_HOSTS)
            os.makedirs(dirname, exist_ok=True)
            open(settings.SSH_KNOWN_HOSTS, 'a')

            client = SSHClient()
            client.load_host_keys(settings.SSH_KNOWN_HOSTS)
            client.set_missing_host_key_policy(AutoAddPolicy())
            client.set_log_channel('paramiko')

            # Filter Paramiko message to only show host key messages
            logging.getLogger('paramiko').addFilter(ParamikoLogFilter())

            hostnames = [
                settings.V4_HOST,
                settings.V6_HOST,
                settings.NAT64_HOST
            ]

            for hostname in hostnames:
                logger.info("Connecting to {}".format(hostname))
                client.connect(hostname, key_filename=settings.SSH_PRIVATE_KEY, allow_agent=False, look_for_keys=False)
                stdin, stdout, stderr = client.exec_command('phantomjs --version')
                stdout_lines = stdout.readlines()
                if stdout_lines:
                    logger.info("PhantomJS version: {}".format(stdout_lines[0].strip()))
                else:
                    logger.error(''.join([line.strip() for line in stderr.readlines()][:1]))
                client.close()

        except Exception as e:
            logger.critical(str(e))
