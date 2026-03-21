"""Tests for runtime control fields added to SharedState."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.shared_state import SharedState  # noqa: E402


def test_runtime_control_toggles_and_snapshot() -> None:
    state = SharedState()

    state.set_face_security_enabled(False)
    state.set_voice_listener_enabled(False)
    state.set_gesture_control_enabled(False)
    state.request_mode('System Mode')
    state.set_gesture_status('Stable')
    state.set_activation_lock(True, 'Face not authorized')

    snap = state.snapshot()
    assert snap['face_security_enabled'] is False
    assert snap['voice_listener_enabled'] is False
    assert snap['gesture_control_enabled'] is False
    assert snap['requested_mode'] == 'System Mode'
    assert snap['gesture_status'] == 'Stable'
    assert snap['activation_locked'] is True
    assert snap['activation_lock_reason'] == 'Face not authorized'
