"""
Module: logger.py
Description: Asynchronous runtime logging helpers for MMGI.

Why async logging?
------------------
MMGI processes camera frames in a tight loop. Writing directly to disk from
that loop can add jitter, so we push log records onto a queue and flush them
from a background listener thread.
"""

from __future__ import annotations

import atexit
import logging
import logging.handlers
from pathlib import Path
from queue import Queue

LOGGER_NAME = 'mmgi.runtime'
LOG_FILENAME = 'mmgi.log'
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3

_mmgi_logger: logging.Logger | None = None
_log_listener: logging.handlers.QueueListener | None = None


def _log_file_path() -> Path:
    """Return the canonical runtime log file path (and ensure parent exists)."""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / LOG_FILENAME


def _build_file_handler() -> logging.Handler:
    """Create the rotating file handler used by the queue listener."""
    file_handler = logging.handlers.RotatingFileHandler(
        str(_log_file_path()),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    )
    return file_handler


def _build_mmgi_logger() -> logging.Logger:
    """Initialise and return the process-wide asynchronous MMGI logger."""
    global _log_listener

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    log_record_queue: Queue = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_record_queue)
    file_handler = _build_file_handler()

    _log_listener = logging.handlers.QueueListener(
        log_record_queue,
        file_handler,
        respect_handler_level=True,
    )
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


def log_gesture_detected(gesture_name: str) -> None:
    """Log a confirmed, stable gesture."""
    get_mmgi_logger().info('Gesture detected: %s', gesture_name)


def log_action_executed(action_label: str) -> None:
    """Log an executed action label for audit/debug traces."""
    get_mmgi_logger().info('Action executed: %s', action_label)


def log_low_confidence(confidence: float) -> None:
    """Log weak detections that are intentionally ignored."""
    get_mmgi_logger().warning('Low confidence gesture (confidence=%.2f)', confidence)


def log_pipeline_state(message: str) -> None:
    """Log pipeline lifecycle events such as started/stopped."""
    get_mmgi_logger().info(message)


def log_input_received(input_type: str, command: str, confidence: float) -> None:
    """Log each normalized input entering the decision pipeline."""
    get_mmgi_logger().info(
        'Input received: type=%s command=%s confidence=%.3f',
        input_type,
        command,
        confidence,
    )


def log_decision_made(mode: str, command: str, action: str | None, reason: str | None = None) -> None:
    """Log decision engine output before execution/security gating."""
    get_mmgi_logger().info(
        'Decision made: mode=%s command=%s action=%s reason=%s',
        mode,
        command,
        action,
        reason,
    )


def log_security_check(allowed: bool, details: str) -> None:
    """Log security authorization pass/fail checks."""
    get_mmgi_logger().info('Security check: allowed=%s details=%s', allowed, details)


def log_runtime_error(message: str) -> None:
    """Log runtime errors while keeping call sites concise."""
    get_mmgi_logger().error(message)
