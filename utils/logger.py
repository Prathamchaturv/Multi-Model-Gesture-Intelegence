"""
Module: logger.py
Description: Asynchronous logging utilities for MMGI runtime events.

Creates logs/mmgi.log and writes gesture/action/error telemetry with a
non-blocking QueueHandler + QueueListener setup to avoid pipeline slowdowns.
"""

from __future__ import annotations

import atexit
import logging
import logging.handlers
from pathlib import Path
from queue import Queue

_mmgi_logger: logging.Logger | None = None
_log_listener: logging.handlers.QueueListener | None = None


def _build_mmgi_logger() -> logging.Logger:
    """Initialise and return the process-wide asynchronous MMGI logger."""
    global _log_listener

    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'mmgi.log'

    logger = logging.getLogger('mmgi.runtime')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    record_queue: Queue = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(record_queue)

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    )

    _log_listener = logging.handlers.QueueListener(record_queue, file_handler, respect_handler_level=True)
    _log_listener.start()
    atexit.register(_stop_listener)

    logger.addHandler(queue_handler)
    return logger


def _stop_listener() -> None:
    """Stop the background queue listener during process shutdown."""
    global _log_listener
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None


def get_mmgi_logger() -> logging.Logger:
    """Return singleton logger for runtime events and errors."""
    global _mmgi_logger
    if _mmgi_logger is None:
        _mmgi_logger = _build_mmgi_logger()
    return _mmgi_logger


def get_performance_logger() -> logging.Logger:
    """Backward-compatible alias retained for existing callers."""
    return get_mmgi_logger()
