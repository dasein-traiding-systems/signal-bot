import logging
import os
import traceback
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from config import Config, LOG_FORMAT

def append_formatter(handler: Any, logging_level: Any = logging.INFO):
    handler.setLevel(logging_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def get_file_handler(
    file_name: str, logging_level: Any = logging.INFO
) -> logging.FileHandler:
    file_handler = logging.FileHandler(file_name)
    return append_formatter(file_handler, logging_level)


def get_stream_handler(logging_level: Any = logging.INFO) -> logging.StreamHandler:
    stream_handler = logging.StreamHandler()
    return append_formatter(stream_handler, logging_level)


def get_rotating_file_handler(file_name: str, logging_level: Any = logging.INFO):
    file_handler = RotatingFileHandler(file_name, maxBytes=1000000, backupCount=3)
    return append_formatter(file_handler, logging_level)


def setup_logger(name: Optional[str] = None, logging_level: Any = logging.INFO, global_logger_name: str = "global",
                 config: Optional[Config] = None):
    logger = logging.getLogger(name)
    logger.setLevel(logging_level)
    if len(logger.handlers) == 0:
        if config is not None:
            log_name = name or global_logger_name
            file_name = os.path.expanduser(f"{config.LOGS_PATH}/{log_name}.log")

            logger.addHandler(get_rotating_file_handler(file_name, logging_level))

        if name is None:
            logger.addHandler(get_stream_handler(logging_level))

    return logger


def add_traceback(msg):
    return "{msg}\r\n{traceback}".format(msg=msg, traceback=traceback.format_exc())