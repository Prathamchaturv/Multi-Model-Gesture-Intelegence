"""
tests/test_mode_switching.py - Unit tests for Smart Mode switching logic

Tests the DecisionEngine's mode-cycling behaviour and the integrated
SystemModeEngine coordinator.

Run:
    python -m pytest tests/test_mode_switching.py -v
    # or
    python tests/test_mode_switching.py
"""

import sys
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from engine.decision_engine     import DecisionEngine, MODES, DEFAULT_MODE, STABILITY_FRAMES, HOLD_SECONDS, COOLDOWN_SECONDS
from core.system_mode_engine    import SystemModeEngine


# ---------------------------------------------------------------------------
# DecisionEngine tests
# ---------------------------------------------------------------------------

class TestDecisionEngineModeSwitching(unittest.TestCase):
    """Tests for mode-cycle logic inside DecisionEngine."""

    def setUp(self) -> None:
        self.engine = DecisionEngine()

    def test_initial_mode_is_app_mode(self) -> None:
        self.assertEqual(self.engine.current_mode, DEFAULT_MODE)

    def test_non_switch_gesture_returns_action(self) -> None:
        # 'One Finger' maps to 'open_brave' in App Mode by default
        action, mode_changed = self.engine.process('One Finger')
        self.assertEqual(action, 'open_brave')
        self.assertFalse(mode_changed)

    def test_none_gesture_returns_no_action(self) -> None:
        action, mode_changed = self.engine.process(None)
        self.assertIsNone(action)
        self.assertFalse(mode_changed)

    def test_mode_switch_gesture_is_detected(self) -> None:
        self.assertTrue(self.engine.is_mode_switch('Three Fingers'))
        self.assertFalse(self.engine.is_mode_switch('One Finger'))

    def test_mode_switches_after_hold(self) -> None:
        """Holding Three Fingers for STABILITY_FRAMES frames + HOLD_SECONDS should switch mode."""
        # Patch time so we can control it
        start = time.time()
        with patch('engine.decision_engine.time') as mock_time:
            mock_time.time.return_value = start

            # Feed enough frames to reach frame stability threshold
            for i in range(STABILITY_FRAMES):
                mock_time.time.return_value = start + (HOLD_SECONDS * i / STABILITY_FRAMES)
                self.engine.process('Three Fingers')

            # Now also satisfy time threshold
            mock_time.time.return_value = start + HOLD_SECONDS + 0.1
            _, mode_changed = self.engine.process('Three Fingers')

        self.assertTrue(mode_changed)
        self.assertEqual(self.engine.current_mode, MODES[1])  # App → Media

    def test_mode_cycles_through_all_three(self) -> None:
        """After 3 switches we should be back at App Mode."""
        def force_switch(eng: DecisionEngine) -> None:
            """Drive engine to switch mode by fast-forwarding hold logic."""
            start = 999.0
            with patch('engine.decision_engine.time') as mock_time:
                mock_time.time.return_value = start + 2.0  # past cooldown
                for i in range(STABILITY_FRAMES + 1):
                    mock_time.time.return_value = start + 2.0 + HOLD_SECONDS + i * 0.01
                    eng.process('Three Fingers')

        for _ in range(3):
            force_switch(self.engine)

        self.assertEqual(self.engine.current_mode, 'App Mode')

    def test_cooldown_prevents_immediate_re_switch(self) -> None:
        """A second switch gesture right after a switch should be ignored during cooldown."""
        def force_switch(eng: DecisionEngine, base_time: float) -> None:
            with patch('engine.decision_engine.time') as mock_time:
                mock_time.time.return_value = base_time
                for i in range(STABILITY_FRAMES + 1):
                    mock_time.time.return_value = base_time + HOLD_SECONDS + i * 0.01
                    eng.process('Three Fingers')

        force_switch(self.engine, 1000.0)
        mode_after_first = self.engine.current_mode

        # Immediate second switch attempt (no time elapsed → cooldown still active)
        force_switch(self.engine, 1000.0)
        self.assertEqual(self.engine.current_mode, mode_after_first)

    def test_switch_debounce_requires_full_cooldown(self) -> None:
        """Mode must not switch again until the 2-second cooldown has fully elapsed."""
        eng = DecisionEngine()

        with patch('engine.decision_engine.time') as mock_time:
            # First successful switch to Media Mode
            start = 100.0
            for i in range(STABILITY_FRAMES + 1):
                mock_time.time.return_value = start + i * 0.12
                eng.process('Three Fingers')
            self.assertEqual(eng.current_mode, 'Media Mode')

            # Still inside cooldown window: should remain Media Mode
            within_cooldown = start + HOLD_SECONDS + COOLDOWN_SECONDS - 0.05
            for i in range(STABILITY_FRAMES + 1):
                mock_time.time.return_value = within_cooldown + i * 0.12
                eng.process('Three Fingers')
            self.assertEqual(eng.current_mode, 'Media Mode')

            # After cooldown: switch should be allowed to System Mode
            after_cooldown = start + HOLD_SECONDS + COOLDOWN_SECONDS + 0.2
            for i in range(STABILITY_FRAMES + 1):
                mock_time.time.return_value = after_cooldown + i * 0.12
                eng.process('Three Fingers')
            self.assertEqual(eng.current_mode, 'System Mode')

    def test_stability_resets_on_gesture_change(self) -> None:
        self.engine.process('Three Fingers')
        self.engine.process(None)   # gesture changed → stability should reset
        # After a reset, mode shouldn't switch with just a few frames
        for _ in range(3):
            action, mode_changed = self.engine.process('Three Fingers')
        self.assertFalse(mode_changed)

    def test_get_action_for_media_mode(self) -> None:
        # Force mode to Media Mode
        self.engine.current_mode = 'Media Mode'
        action = self.engine.get_action('One Finger', 'Media Mode')
        self.assertEqual(action, 'volume_up')

    def test_unknown_gesture_returns_none_action(self) -> None:
        action, _ = self.engine.process('Unknown')
        self.assertIsNone(action)

    def test_hot_reload_updates_action_mapping_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / 'gesture_map.json'

            initial = {
                'mode_switch': {'Three Fingers': 'next_mode'},
                'App Mode': {'One Finger': 'open_brave'},
                'Media Mode': {},
                'System Mode': {},
            }
            updated = {
                'mode_switch': {'Three Fingers': 'next_mode'},
                'App Mode': {'One Finger': 'open_apple_music'},
                'Media Mode': {},
                'System Mode': {},
            }

            with open(cfg_path, 'w', encoding='utf-8') as fh:
                json.dump(initial, fh)

            eng = DecisionEngine(config_path=cfg_path)
            self.assertEqual(eng.get_action('One Finger', 'App Mode'), 'open_brave')

            time.sleep(0.6)
            with open(cfg_path, 'w', encoding='utf-8') as fh:
                json.dump(updated, fh)

            time.sleep(0.6)
            eng.process(None)  # trigger reload check
            self.assertEqual(eng.get_action('One Finger', 'App Mode'), 'open_apple_music')


# ---------------------------------------------------------------------------
# SystemModeEngine integration tests
# ---------------------------------------------------------------------------

class TestSystemModeEngine(unittest.TestCase):
    """Integration tests for the high-level SystemModeEngine."""

    def test_initial_state(self) -> None:
        engine = SystemModeEngine()
        self.assertEqual(engine.current_mode, 'App Mode')
        self.assertFalse(engine.is_active)
        self.assertFalse(engine.in_cooldown)
        self.assertAlmostEqual(engine.mode_stability_progress, 0.0)

    def test_process_returns_result_object(self) -> None:
        from core.system_mode_engine import ModeEngineResult
        engine = SystemModeEngine()
        result = engine.process(None)
        self.assertIsInstance(result, ModeEngineResult)

    def test_no_action_when_inactive(self) -> None:
        """Actions should not fire when the system is not yet activated."""
        engine = SystemModeEngine()
        result = engine.process('One Finger')
        self.assertIsNone(result.action)

    def test_status_summary_keys(self) -> None:
        engine = SystemModeEngine()
        summary = engine.status_summary()
        for key in ('mode', 'active', 'cooldown', 'stability', 'timestamp'):
            self.assertIn(key, summary)

    def test_air_mouse_property_returns_controller(self) -> None:
        from core.system_mode_engine import AirMouseController
        engine = SystemModeEngine()
        self.assertIsInstance(engine.air_mouse, AirMouseController)

    def test_modes_tuple_order(self) -> None:
        self.assertEqual(SystemModeEngine.MODES, ('App Mode', 'Media Mode', 'System Mode'))


# ---------------------------------------------------------------------------
# Simple function-style tests (Phase 3 style)
# ---------------------------------------------------------------------------

from engine.decision_engine import get_action  # noqa: E402


def test_app_mode_one_finger():
    assert get_action('App Mode', 'One Finger') == 'open_brave'


def test_app_mode_two_fingers():
    assert get_action('App Mode', 'Two Fingers') == 'open_apple_music'


def test_media_mode_four_fingers():
    assert get_action('Media Mode', 'Four Fingers') == 'play_pause'


def test_media_mode_thumbs_up():
    assert get_action('Media Mode', 'Thumbs Up') == 'mute'


def test_media_mode_volume_down():
    assert get_action('Media Mode', 'Two Fingers') == 'volume_down'


def test_unknown_gesture_returns_none():
    assert get_action('App Mode', 'Unknown') is None


def test_system_mode_one_finger_cursor():
    # System Mode: One Finger gesture now maps to cursor_move
    assert get_action('System Mode', 'One Finger') == 'cursor_move'


def test_system_mode_thumb_index_scroll():
    # System Mode: Thumb and Index gesture maps to continuous scroll_up
    assert get_action('System Mode', 'Thumb and Index') == 'scroll_up'


def test_system_mode_thumb_index_middle_scroll():
    # System Mode: Thumb, Index and Middle gesture maps to scroll_down
    assert get_action('System Mode', 'Thumb, Index and Middle') == 'scroll_down'


# ---------------------------------------------------------------------------
# AirMouseController unit tests  (Win32 calls are mocked)
# ---------------------------------------------------------------------------

class _MockUser32:
    """Minimal mock for ctypes.windll.user32 used by AirMouseController."""
    def __init__(self, screen_w: int = 1920, screen_h: int = 1080) -> None:
        self._sw = screen_w
        self._sh = screen_h
        self.cursor_x = 0
        self.cursor_y = 0
        self.mouse_events: list[tuple] = []

    def GetSystemMetrics(self, idx: int) -> int:
        return self._sw if idx == 0 else self._sh

    def SetCursorPos(self, x: int, y: int) -> None:
        self.cursor_x, self.cursor_y = x, y

    def GetCursorPos(self, ptr) -> None:
        ptr.x, ptr.y = self.cursor_x, self.cursor_y

    def mouse_event(self, flags, x, y, data, extra) -> None:
        self.mouse_events.append((flags, data))


def _make_air_mouse(mock_u32: _MockUser32 | None = None):
    """Helper: create AirMouseController with mocked Win32 layer."""
    import ctypes, ctypes.wintypes
    from core.system_mode_engine import AirMouseController

    if mock_u32 is None:
        mock_u32 = _MockUser32()

    with patch('ctypes.windll') as mock_dll:
        mock_dll.user32 = mock_u32
        ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=0.0)
    # Patch the live user32 reference inside the already-created object
    ctrl.__dict__['_screen_w'] = mock_u32._sw
    ctrl.__dict__['_screen_h']  = mock_u32._sh

    # Replace ctypes calls with mock
    import core.system_mode_engine as sme_mod
    ctrl._u32 = mock_u32
    return ctrl, mock_u32, sme_mod


class TestAirMouseController(unittest.TestCase):
    """Unit tests for AirMouseController; Win32 calls are mocked via module patch."""

    def _make(self):
        from core.system_mode_engine import AirMouseController
        import ctypes.wintypes as wt

        mock_u32 = _MockUser32()

        # Patch the module-level ctypes.windll and ctypes.wintypes.POINT
        mock_point = MagicMock()
        mock_point.x = 0
        mock_point.y = 0

        with patch('core.system_mode_engine.ctypes') as mock_ctypes:
            mock_ctypes.windll.user32 = mock_u32
            mock_ctypes.wintypes.POINT.return_value = mock_point
            ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=0.0)

        ctrl._screen_w = mock_u32._sw
        ctrl._screen_h = mock_u32._sh
        return ctrl, mock_u32, mock_point

    def _landmarks(self, index_x: float, index_y: float) -> list:
        """Build a minimal 21-landmark list with landmark 8 at the given coords."""
        lms = [(0.5, 0.5, 0.0)] * 21
        lms[8] = (index_x, index_y, 0.0)
        return lms

    def test_empty_landmarks_returns_none(self) -> None:
        ctrl, *_ = self._make()
        result = ctrl.update([], {}, 'One Finger', 640, 480)
        self.assertIsNone(result)

    def test_reset_clears_state(self) -> None:
        ctrl, *_ = self._make()
        ctrl._smooth_x = 100.0
        ctrl._smooth_y = 200.0
        ctrl._scroll_ref_y = 0.5
        ctrl._prev_gesture = 'Pinky'
        ctrl.reset()
        self.assertIsNone(ctrl._smooth_x)
        self.assertIsNone(ctrl._smooth_y)
        self.assertIsNone(ctrl._scroll_ref_y)
        self.assertIsNone(ctrl._prev_gesture)

    def test_click_respects_cooldown(self) -> None:
        from core.system_mode_engine import AirMouseController
        import ctypes.wintypes as wt

        mock_u32 = _MockUser32()
        mock_point = MagicMock(); mock_point.x = 0; mock_point.y = 0

        with patch('core.system_mode_engine.ctypes') as mc:
            mc.windll.user32 = mock_u32
            mc.wintypes.POINT.return_value = mock_point
            ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=10.0)

        ctrl._screen_w = mock_u32._sw
        ctrl._screen_h = mock_u32._sh
        ctrl._last_click_time = time.time()  # set cooldown active
        self.assertFalse(ctrl._cooldown_ok())

    def test_cooldown_expires(self) -> None:
        from core.system_mode_engine import AirMouseController
        mock_u32 = _MockUser32()
        mock_point = MagicMock(); mock_point.x = 0; mock_point.y = 0

        with patch('core.system_mode_engine.ctypes') as mc:
            mc.windll.user32 = mock_u32
            mc.wintypes.POINT.return_value = mock_point
            ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=0.0)

        ctrl._screen_w = mock_u32._sw
        ctrl._screen_h = mock_u32._sh
        ctrl._last_click_time = 0.0   # long ago
        self.assertTrue(ctrl._cooldown_ok())

    def test_scroll_anchor_set_on_first_frame(self) -> None:
        from core.system_mode_engine import AirMouseController
        mock_u32 = _MockUser32()
        mock_point = MagicMock(); mock_point.x = 0; mock_point.y = 0

        with patch('core.system_mode_engine.ctypes') as mc:
            mc.windll.user32 = mock_u32
            mc.wintypes.POINT.return_value = mock_point
            ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=0.0)

        ctrl._screen_w = mock_u32._sw
        ctrl._screen_h = mock_u32._sh
        lms = [(0.5, 0.5, 0.0)] * 21; lms[8] = (0.5, 0.4, 0.0)
        # First call should set anchor and return None
        with patch('core.system_mode_engine.ctypes') as mc2:
            mc2.windll.user32 = mock_u32
            mc2.wintypes.POINT.return_value = mock_point
            result = ctrl._scroll(lms)
        self.assertIsNone(result)
        self.assertAlmostEqual(ctrl._scroll_ref_y, 0.4)

    def test_prev_gesture_edge_detection(self) -> None:
        """Click gestures only fire on rising edge (not held)."""
        from core.system_mode_engine import AirMouseController
        mock_u32  = _MockUser32()
        mock_point = MagicMock(); mock_point.x = 0; mock_point.y = 0

        with patch('core.system_mode_engine.ctypes') as mc:
            mc.windll.user32  = mock_u32
            mc.wintypes.POINT.return_value = mock_point
            ctrl = AirMouseController(smoothing=1.0, dead_zone=0, click_cooldown=0.0)

        ctrl._screen_w   = mock_u32._sw
        ctrl._screen_h   = mock_u32._sh
        ctrl._prev_gesture = 'Pinky'   # simulate gesture already held

        lms = [(0.5, 0.5, 0.0)] * 21
        with patch('core.system_mode_engine.ctypes') as mc2:
            mc2.windll.user32  = mock_u32
            mc2.wintypes.POINT.return_value = mock_point
            result = ctrl.update(lms, {}, 'Pinky', 640, 480)
        # Should NOT fire — gesture is held, not a rising edge
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
