"""Pipeline lifecycle management for MMGI runtime."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from ui.worker_thread import WorkerThread
from utils.logger import log_pipeline_state, log_runtime_error


class PipelineLifecycleManager(QObject):
    """Owns worker lifecycle with start/stop/restart semantics."""

    state_changed = pyqtSignal(str)
    worker_changed = pyqtSignal(object)

    STOPPED = 'STOPPED'
    STARTING = 'STARTING'
    RUNNING = 'RUNNING'
    STOPPING = 'STOPPING'
    ERROR = 'ERROR'

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = self.STOPPED
        self._worker: WorkerThread | None = None
        self.state_changed.emit(self._state)

    @property
    def state(self) -> str:
        return self._state

    @property
    def worker(self) -> WorkerThread | None:
        return self._worker

    def start(self, worker_factory: Callable[[], WorkerThread]) -> bool:
        if self._worker is not None and self._worker.isRunning():
            return True

        self._set_state(self.STARTING)
        try:
            worker = worker_factory()
            worker.start()
            self._worker = worker
            self.worker_changed.emit(worker)
            self._set_state(self.RUNNING)
            log_pipeline_state('Lifecycle: pipeline started')
            return True
        except Exception as exc:
            self._worker = None
            self._set_state(self.ERROR)
            log_runtime_error(f'Lifecycle start failed: {exc}')
            return False

    def stop(self, timeout_ms: int = 3000) -> bool:
        if self._worker is None:
            self._set_state(self.STOPPED)
            return True

        if not self._worker.isRunning():
            self._worker = None
            self.worker_changed.emit(None)
            self._set_state(self.STOPPED)
            return True

        self._set_state(self.STOPPING)
        self._worker.stop()
        finished = self._worker.wait(timeout_ms)
        if not finished:
            log_runtime_error('Lifecycle stop timeout: worker did not stop gracefully')
            self._set_state(self.ERROR)
            return False

        self._worker = None
        self.worker_changed.emit(None)
        self._set_state(self.STOPPED)
        log_pipeline_state('Lifecycle: pipeline stopped')
        return True

    def restart(self, worker_factory: Callable[[], WorkerThread], timeout_ms: int = 3000) -> bool:
        stopped = self.stop(timeout_ms=timeout_ms)
        if not stopped:
            return False
        return self.start(worker_factory)

    def _set_state(self, new_state: str) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(new_state)
