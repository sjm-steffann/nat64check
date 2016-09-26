import logging


def init_logging(logger, verbosity):
    if verbosity > 0:
        console = logging.StreamHandler()
        try:
            # noinspection PyUnresolvedReferences
            from colorlog import ColoredFormatter
            formatter = ColoredFormatter('{yellow}{asctime}{reset} '
                                         '[{log_color}{levelname}{reset}] '
                                         '{white}{message}{reset}',
                                         style='{')

        except ImportError:
            formatter = logging.Formatter('{asctime} [{levelname}] {message}',
                                          style='{')

        console.setFormatter(formatter)
        console.setLevel(logging.DEBUG)
        logger.addHandler(console)

        # Stop PIL from excessive logging
        pil_logger = logging.getLogger('PIL')
        pil_logger.setLevel(logging.INFO)

    if verbosity >= 2:
        logger.setLevel(logging.INFO)

    if verbosity >= 3:
        logger.setLevel(logging.DEBUG)
