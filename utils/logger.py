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
PERF_LOGGER_NAME = 'mmgi.performance'
LOG_FILENAME = 'mmgi.log'
PERF_LOG_FILENAME = 'mmgi_performance.log'
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3

_mmgi_logger: logging.Logger | None = None
_performance_logger: logging.Logger | None = None
_log_listener: logging.handlers.QueueListener | None = None


def _log_file_path() -> Path:
    """Return the canonical runtime log file path (and ensure parent exists)."""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / LOG_FILENAME


def _performance_log_file_path() -> Path:
    """Return the canonical performance log file path (and ensure parent exists)."""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / PERF_LOG_FILENAME


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


def _build_performance_file_handler() -> logging.Handler:
    """Create rotating file handler dedicated to frame/performance telemetry."""
    perf_handler = logging.handlers.RotatingFileHandler(
        str(_performance_log_file_path()),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.addFilter(lambda record: record.name.startswith(PERF_LOGGER_NAME))
    perf_handler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            datefmt='%H:%M:%S',
        )
    )
    return perf_handler


def _build_console_handler() -> logging.Handler:
    """Create console handler for local observability while developing/running MMGI."""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            datefmt='%H:%M:%S',
        )
    )
    return console_handler


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
    perf_file_handler = _build_performance_file_handler()
    console_handler = _build_console_handler()

    _log_listener = logging.handlers.QueueListener(
        log_record_queue,
        file_handler,
        perf_file_handler,
        console_handler,
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
    """Return singleton logger dedicated to performance telemetry."""
    global _performance_logger
    if _performance_logger is None:
        get_mmgi_logger()  # ensure queue listener is initialized
        logger = logging.getLogger(PERF_LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            queue_logger = get_mmgi_logger()
            for handler in queue_logger.handlers:
                logger.addHandler(handler)
        _performance_logger = logger
    return _performance_logger


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


def log_face_authorization_event(allowed: bool, status_text: str, similarity: float | None = None) -> None:
    """Log explicit face authorization outcomes."""
    if similarity is None:
        get_mmgi_logger().info('Face auth: allowed=%s status=%s', allowed, status_text)
    else:
        get_mmgi_logger().info(
            'Face auth: allowed=%s status=%s similarity=%.3f',
            allowed,
            status_text,
            similarity,
        )


def log_voice_command_event(command: str, mapped: bool, details: str = '') -> None:
    """Log recognized voice commands and mapping status."""
    get_mmgi_logger().info(
        'Voice command: command=%s mapped=%s details=%s',
        command,
        mapped,
        details,
    )


def log_lifecycle_event(stage: str, status: str, details: str = '') -> None:
    """Log lifecycle transitions such as start/stop/restart."""
    get_mmgi_logger().info('Lifecycle: stage=%s status=%s details=%s', stage, status, details)


def log_runtime_error(message: str) -> None:
    """Log runtime errors while keeping call sites concise."""
    get_mmgi_logger().error(message)


def log_runtime_warning(message: str) -> None:
    """Log runtime warnings while keeping call sites concise."""
    get_mmgi_logger().warning(message)


def log_frame_drop(reason: str, count: int = 1, queue_size: int | None = None) -> None:
    """Log frame drops caused by queue overflow, stale-drop, or budget pressure."""
    if queue_size is None:
        get_mmgi_logger().warning('Frame drop: reason=%s count=%d', reason, count)
        return
    get_mmgi_logger().warning(
        'Frame drop: reason=%s count=%d queue_size=%d',
        reason,
        count,
        queue_size,
    )


def log_frame_latency(frame_index: int, latency_ms: float, fps: float, mode: str) -> None:
    """Log per-frame processing latency for performance monitoring."""
    get_performance_logger().info(
        'Frame latency: frame=%d latency_ms=%.2f fps=%.1f mode=%s',
        frame_index,
        latency_ms,
        fps,
        mode,
    )
