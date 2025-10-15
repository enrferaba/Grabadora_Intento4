"""Logging bootstrap helpers."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import PATHS


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("transcriptor")
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(PATHS.log_file, maxBytes=1_000_000, backupCount=3)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(fmt)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
