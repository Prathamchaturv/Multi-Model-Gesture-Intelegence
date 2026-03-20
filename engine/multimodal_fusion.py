"""
Gesture + voice fusion gate for Media Mode actions.
"""

from __future__ import annotations

import time


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
