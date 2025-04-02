import argparse
import logging


class Logger:
    log_format = logging.Formatter(
        fmt="%(asctime)s | %(name)-11s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    arg_log_level = None
    arg_log_file = None

    @classmethod
    def init(cls, args: argparse.Namespace):
        logger = logging.getLogger()

        if args.__dict__.get("log_level") is not None:
            level = logging.getLevelNamesMapping()[args.log_level]
            logger.setLevel(level)
            cls.arg_log_level = level
        else:
            logger.setLevel(logging.DEBUG)

        for handler in logger.handlers:
            logger.removeHandler(handler)

        if args.__dict__.get("log_file") is not None:
            log_handler = logging.FileHandler(args.log_file)
            cls.arg_log_file = args.log_file
        else:
            log_handler = logging.StreamHandler()

        log_handler.setFormatter(cls.log_format)
        logger.addHandler(log_handler)

        logger.name = args.command

        cls.instance = logger

    @classmethod
    def update_from_config(cls, config):
        logger = cls.instance

        if cls.arg_log_level is None and config.log_level is not None:
            level = logging.getLevelNamesMapping()[config.log_level]
            logger.setLevel(level)

        if cls.arg_log_file is None and config.log_file is not None:
            log_handler = logging.FileHandler(config.log_file)
            log_handler.setFormatter(cls.log_format)

            for handler in logger.handlers:
                logger.removeHandler(handler)

            logger.addHandler(log_handler)

    @classmethod
    def get(cls):
        return cls.instance
