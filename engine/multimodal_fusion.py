"""
Gesture + voice fusion gate for Media Mode actions.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from engine.unified_pipeline import InputEvent


class MultiModalFusionEngine:
    """Requires voice + gesture agreement for selected Media Mode actions."""

    def __init__(
        self,
        required_actions: set[str] | None = None,
        action_voice_map: dict[str, set[str]] | None = None,
        command_ttl_s: float = 2.5,
    ) -> None:
        self._required_actions = required_actions or {'play_pause', 'mute'}
        self._action_voice_map = action_voice_map or {
            'play_pause': {'play_song', 'pause'},
            'mute': {'mute'},
            'next_track': {'next_track'},
            'prev_track': {'previous_track'},
            'volume_up': {'volume_up'},
            'volume_down': {'volume_down'},
        }
        self._command_ttl_s = float(command_ttl_s)
        self._last_command: str | None = None
        self._last_ts: float = 0.0

    def update_voice(self, command: str, ts: float | None = None) -> None:
        self._last_command = command
        self._last_ts = time.time() if ts is None else float(ts)

    def resolve(self, action: str | None, mode: str, ts: float | None = None) -> tuple[bool, str | None]:
        """Return (allow_execute, matched_voice_command)."""
        if not action:
            return False, None

        if mode != 'Media Mode' or action not in self._required_actions:
            return True, None

        now = time.time() if ts is None else float(ts)
        if not self._last_command:
            return False, None

        if (now - self._last_ts) > self._command_ttl_s:
            self._last_command = None
            return False, None

        expected = self._action_voice_map.get(action, set())
        if self._last_command in expected:
            matched = self._last_command
            self._last_command = None
            return True, matched

        return False, None


@dataclass(frozen=True)
class FusionPolicy:
    """Policy knobs for resolving near-simultaneous gesture/voice input."""

    voice_priority: bool = True
    suppress_unstable_gesture_on_voice: bool = True
    duplicate_window_s: float = 0.3
    allow_parallel_non_duplicate: bool = False


class MultimodalFusionLayer:
    """
    Fuses gesture and voice events before they enter the decision pipeline.

    Default behavior:
    - Voice has priority.
    - Unstable gesture is dropped when voice is present.
    - Duplicate command in a short window is deduplicated.
    """

    def __init__(self, policy: FusionPolicy | None = None) -> None:
        self._policy = policy or FusionPolicy()

    def merge(
        self,
        *,
        gesture_event: InputEvent | None,
        voice_event: InputEvent | None,
        gesture_is_stable: bool,
        uncertainty_lock_active: bool,
    ) -> list[InputEvent]:
        """Return ordered events to process in the unified pipeline."""
        events: list[InputEvent] = []

        if voice_event is not None:
            events.append(voice_event)

        if gesture_event is None:
            return events

        if uncertainty_lock_active:
            return events

        if voice_event is not None:
            if self._policy.suppress_unstable_gesture_on_voice and not gesture_is_stable:
                return events

            if self._is_duplicate(gesture_event, voice_event):
                if self._policy.voice_priority:
                    return events

            if not self._policy.allow_parallel_non_duplicate and self._policy.voice_priority:
                return events

        events.append(gesture_event)
        return events

    def _is_duplicate(self, gesture_event: InputEvent, voice_event: InputEvent) -> bool:
        if gesture_event.command != voice_event.command:
            return False
        return abs(gesture_event.timestamp - voice_event.timestamp) <= self._policy.duplicate_window_s
