"""Unit tests for context-aware gesture routing."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from engine.context_aware_gesture import ActiveWindowInfo, get_context, handle_gesture


class TestContextClassification(unittest.TestCase):
    def test_browser_context_from_process_name(self) -> None:
        info = ActiveWindowInfo(
            title='Docs - Example',
            process_name='chrome.exe',
            executable='C:/Program Files/Google/Chrome/Application/chrome.exe',
        )
        with patch('engine.context_aware_gesture._CACHE_REFRESH_S', 0.0):
            self.assertEqual(get_context(info), 'browser')

    def test_media_context_from_window_title(self) -> None:
        info = ActiveWindowInfo(
            title='YouTube - Video Playing',
            process_name='chrome.exe',
            executable='C:/Program Files/Google/Chrome/Application/chrome.exe',
        )
        with patch('engine.context_aware_gesture._CACHE_REFRESH_S', 0.0):
            self.assertEqual(get_context(info), 'media')

    def test_system_context_fallback(self) -> None:
        info = ActiveWindowInfo(
            title='Visual Studio Code',
            process_name='Code.exe',
            executable='C:/Users/User/AppData/Local/Programs/Microsoft VS Code/Code.exe',
        )
        with patch('engine.context_aware_gesture._CACHE_REFRESH_S', 0.0):
            self.assertEqual(get_context(info), 'system')

    def test_media_context_from_configurable_keywords(self) -> None:
        info = ActiveWindowInfo(
            title='Cinema App - Watching',
            process_name='CinemaApp.exe',
            executable='C:/Apps/CinemaApp.exe',
        )
        with patch('engine.context_aware_gesture._load_keywords_from_config', return_value=({'chrome'}, {'cinemaapp'})):
            with patch('engine.context_aware_gesture._CACHE_REFRESH_S', 0.0):
                self.assertEqual(get_context(info), 'media')


class TestGestureRouting(unittest.TestCase):
    def test_browser_swipe_maps_to_scroll(self) -> None:
        self.assertEqual(handle_gesture('Swipe Down', 'browser'), 'scroll_down')

    def test_media_swipe_maps_to_seek(self) -> None:
        self.assertEqual(handle_gesture('swipe_right', 'media'), 'seek_forward')

    def test_system_swipe_maps_to_app_switch(self) -> None:
        self.assertEqual(handle_gesture('swipe_left', 'system'), 'switch_apps')

    def test_unknown_gesture_returns_none(self) -> None:
        self.assertIsNone(handle_gesture('pinch', 'browser'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
