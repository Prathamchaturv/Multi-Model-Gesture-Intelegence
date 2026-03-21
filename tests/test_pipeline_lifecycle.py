"""Tests for pipeline lifecycle management."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.pipeline_lifecycle import PipelineLifecycleManager  # noqa: E402


class _DummyWorker:
    def __init__(self, stop_success: bool = True):
        self._running = False
        self._stop_success = stop_success

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def wait(self, timeout_ms: int) -> bool:
        _ = timeout_ms
        return self._stop_success

    def isRunning(self) -> bool:
        return self._running


def test_lifecycle_start_stop_transitions() -> None:
    manager = PipelineLifecycleManager()

    ok_start = manager.start(lambda: _DummyWorker())
    assert ok_start is True
    assert manager.state == manager.RUNNING

    ok_stop = manager.stop(timeout_ms=100)
    assert ok_stop is True
    assert manager.state == manager.STOPPED


def test_lifecycle_restart_transitions() -> None:
    manager = PipelineLifecycleManager()

    manager.start(lambda: _DummyWorker())
    ok_restart = manager.restart(lambda: _DummyWorker(), timeout_ms=100)
    assert ok_restart is True
    assert manager.state == manager.RUNNING


def test_lifecycle_stop_timeout_enters_error() -> None:
    manager = PipelineLifecycleManager()

    manager.start(lambda: _DummyWorker(stop_success=False))
    ok_stop = manager.stop(timeout_ms=100)
    assert ok_stop is False
    assert manager.state == manager.ERROR
