import logging
from logging.handlers import RotatingFileHandler

class Logger:

    log_file_format = logging.Formatter(
        fmt="%(asctime)s | %(name)-11s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_windows_format = logging.Formatter(
        fmt="%(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    @classmethod
    def init(cls, name):
        logger = logging.getLogger()
        logger.setLevel(logging.ERROR)

        for handler in logger.handlers:
            logger.removeHandler(handler)

        log_handler = logging.StreamHandler()
        log_handler.setFormatter(cls.log_file_format)
        logger.addHandler(log_handler)

        logger.name = name

        cls.instance = logger


    @classmethod
    def set_config(cls, config):
        logger = cls.instance

        level = logging.getLevelNamesMapping()[config.log_level]
        logger.setLevel(level)

        if config.log_file is not None or config.log_windows:
            # Remove stdio handler if any other is specified
            for handler in logger.handlers:
                logger.removeHandler(handler)

        if config.log_file is not None:
            log_handler = RotatingFileHandler(config.log_file, maxBytes=config.log_max_bytes, backupCount=config.log_backup_count)
            log_handler.setFormatter(cls.log_file_format)
            logger.addHandler(log_handler)

        if config.log_windows:
            log_handler = logging.handlers.NTEventLogHandler("AD User Sync")
            log_handler.setFormatter(cls.log_windows_format)
            logger.addHandler(log_handler)

    @classmethod
    def get(cls):
        return cls.instance
