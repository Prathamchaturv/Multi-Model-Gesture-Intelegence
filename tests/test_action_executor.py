"""
tests/test_action_executor.py - Unit tests for ActionExecutor

Tests action execution, label lookups, and edge-case behaviour
without triggering real system calls.

Run:
    python -m pytest tests/test_action_executor.py -v
    # or
    python tests/test_action_executor.py
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from engine.action_executor import ActionExecutor


class TestActionExecutorLabels(unittest.TestCase):
    """Verify the human-readable label table is complete and consistent."""

    def test_all_expected_keys_have_labels(self) -> None:
        expected = [
            'open_brave', 'open_apple_music',
            'next_track', 'prev_track', 'play_pause',
            'volume_up', 'volume_down', 'mute',
        ]
        for key in expected:
            with self.subTest(key=key):
                self.assertIn(key, ActionExecutor._LABELS)

    def test_all_key_map_entries_have_labels(self) -> None:
        for key in ActionExecutor._KEY_MAP:
            with self.subTest(key=key):
                self.assertIn(key, ActionExecutor._LABELS)

    def test_labels_are_non_empty_strings(self) -> None:
        for key, label in ActionExecutor._LABELS.items():
            with self.subTest(key=key):
                self.assertIsInstance(label, str)
                self.assertTrue(len(label) > 0)


class TestActionExecutorExecution(unittest.TestCase):
    """Tests for execute() behaviour using mocked system calls."""

    def setUp(self) -> None:
        self.executor = ActionExecutor(config={
            'brave_path': 'fake/brave.exe',
            'apple_music_aumid': 'FakeApp.Aumid',
        })

    def test_execute_open_brave_calls_launch(self) -> None:
        with patch.object(self.executor, '_launch') as mock_launch:
            self.executor.execute('open_brave')
        mock_launch.assert_called_once()

    def test_execute_open_apple_music_calls_launch_store_app(self) -> None:
        with patch.object(self.executor, '_launch_store_app') as mock_launch:
            self.executor.execute('open_apple_music')
        mock_launch.assert_called_once()

    def test_execute_records_last_action(self) -> None:
        with patch.object(self.executor, '_launch'):
            self.executor.execute('open_brave')
        self.assertEqual(self.executor._last_action, 'open_brave')

    def test_execute_updates_last_action_time(self) -> None:
        before = time.time()
        with patch.object(self.executor, '_launch'):
            self.executor.execute('open_brave')
        self.assertGreaterEqual(self.executor._last_action_time, before)

    def test_execute_volume_up_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('volume_up')
        mock_pg.press.assert_called_once_with('volumeup')

    def test_execute_volume_down_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('volume_down')
        mock_pg.press.assert_called_once_with('volumedown')

    def test_execute_play_pause_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('play_pause')
        mock_pg.press.assert_called_once_with('playpause')

    def test_execute_mute_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('mute')
        mock_pg.press.assert_called_once_with('volumemute')

    def test_execute_next_track_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('next_track')
        mock_pg.press.assert_called_once_with('nexttrack')

    def test_execute_prev_track_presses_correct_key(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui') as mock_pg:
            self.executor.execute('prev_track')
        mock_pg.press.assert_called_once_with('prevtrack')

    def test_unknown_action_does_not_raise(self) -> None:
        """Executing an unrecognised action key must not raise an exception."""
        try:
            self.executor.execute('totally_unknown_action_xyz')
        except Exception as exc:
            self.fail(f'execute() raised {exc!r} for an unknown action key')

    def test_execute_sets_last_action_even_for_key_actions(self) -> None:
        with patch('engine.action_executor._PYAUTOGUI', True), \
             patch('engine.action_executor.pyautogui'):
            self.executor.execute('mute')
        self.assertEqual(self.executor._last_action, 'mute')

    def test_global_cooldown_blocks_rapid_different_actions(self) -> None:
        with patch('engine.action_executor.time.time', side_effect=[100.0, 100.2]), \
             patch.object(self.executor, '_launch') as mock_launch, \
             patch.object(self.executor, '_launch_store_app') as mock_store:
            self.executor.execute('open_brave')
            self.executor.execute('open_apple_music')

        mock_launch.assert_called_once()
        mock_store.assert_not_called()


class TestActionExecutorFeedback(unittest.TestCase):
    """Tests for the display_action overlay method."""

    def setUp(self) -> None:
        self.executor = ActionExecutor()

    def test_display_action_returns_frame_unchanged_when_no_action(self) -> None:
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype='uint8')
        result = self.executor.display_action(frame)
        self.assertIs(result, frame)

    def test_display_action_returns_frame_after_timeout(self) -> None:
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype='uint8')
        self.executor._last_action = 'mute'
        # Simulate that the action happened long ago
        self.executor._last_action_time = time.time() - 10.0
        result = self.executor.display_action(frame)
        self.assertIs(result, frame)


if __name__ == '__main__':
    unittest.main(verbosity=2)
