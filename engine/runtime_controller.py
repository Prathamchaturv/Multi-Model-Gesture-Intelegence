"""
Runtime controller for MMGI pipeline orchestration.

Responsibilities
----------------
- Track runtime state: RUNNING / PAUSED / ERROR
- Track latest confidence and configurable execution threshold
- Handle cooldown windows for action execution
- Decide whether an action may execute now

Example
-------
from engine.runtime_controller import RuntimeController, RuntimeState

controller = RuntimeController(min_confidence=0.5, cooldown_seconds=1.0)
controller.set_state(RuntimeState.RUNNING)
controller.update_confidence(0.82)

allowed, reason = controller.can_execute_action(
    action='open_brave',
    face_authorized=True,
    activation_locked=False,
)
if allowed:
    controller.mark_action_executed()
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time


class RuntimeState(str, Enum):
    RUNNING = 'RUNNING'
    PAUSED = 'PAUSED'
    ERROR = 'ERROR'


@dataclass(frozen=True)
class RuntimeDecision:
    allowed: bool
    reason: str | None = None


class RuntimeController:
    """Central authority for runtime state and action permission checks."""

    def __init__(
        self,
        *,
        min_confidence: float = 0.5,
        cooldown_seconds: float = 1.0,
    ) -> None:
        self._state: RuntimeState = RuntimeState.PAUSED
        self._state_reason: str = 'Initializing'
        self._confidence: float = 0.0
        self._min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self._cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._last_action_ts: float = 0.0

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def state_reason(self) -> str:
        return self._state_reason

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def is_cooldown_active(self) -> bool:
        return (time.time() - self._last_action_ts) < self._cooldown_seconds

    @property
    def cooldown_remaining_s(self) -> float:
        remaining = self._cooldown_seconds - (time.time() - self._last_action_ts)
        return max(0.0, remaining)

    def set_state(self, state: RuntimeState, reason: str = '') -> None:
        self._state = RuntimeState(state)
        self._state_reason = reason or self._state.value

    def update_confidence(self, value: float) -> None:
        self._confidence = max(0.0, min(1.0, float(value)))

    def configure(self, *, min_confidence: float | None = None, cooldown_seconds: float | None = None) -> None:
        if min_confidence is not None:
            self._min_confidence = max(0.0, min(1.0, float(min_confidence)))
        if cooldown_seconds is not None:
            self._cooldown_seconds = max(0.0, float(cooldown_seconds))

    def can_execute_action(
        self,
        *,
        action: str | None,
        face_authorized: bool = True,
        activation_locked: bool = False,
        confidence: float | None = None,
    ) -> tuple[bool, str | None]:
        """Evaluate whether executing an action is currently safe/allowed."""
        if not action:
            return False, 'no_action'

        if self._state == RuntimeState.ERROR:
            return False, 'runtime_error'

        if self._state == RuntimeState.PAUSED:
            return False, 'runtime_paused'

        if activation_locked:
            return False, 'activation_locked'

        if not face_authorized:
            return False, 'auth_required'

        conf = self._confidence if confidence is None else max(0.0, min(1.0, float(confidence)))
        if conf < self._min_confidence:
            return False, 'low_confidence'

        if self.is_cooldown_active:
            return False, 'cooldown_active'

        return True, None

    def mark_action_executed(self) -> None:
        self._last_action_ts = time.time()

    def build_runtime_snapshot(self) -> dict:
        return {
            'state': self._state.value,
            'state_reason': self._state_reason,
            'confidence': self._confidence,
            'min_confidence': self._min_confidence,
            'cooldown_active': self.is_cooldown_active,
            'cooldown_remaining_s': self.cooldown_remaining_s,
        }
