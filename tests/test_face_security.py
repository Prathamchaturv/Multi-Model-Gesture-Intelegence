"""
Unit tests for System Mode face-based security.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.face_security import FaceSecurityManager  # noqa: E402
from engine.activation_manager import ActivationManager  # noqa: E402


class TestFaceSecurityManager(unittest.TestCase):
    def _make_manager(self, enabled: bool = True, threshold: float = 0.84):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        base = Path(td.name)
        encoding_path = base / 'authorized_face_encoding.json'

        mgr = FaceSecurityManager(
            enabled=enabled,
            authorized_image_path=str(base / 'authorized_face.jpg'),
            authorized_encoding_path=str(encoding_path),
            similarity_threshold=threshold,
            min_detection_confidence=0.5,
            eval_interval_s=0.0,
        )
        return mgr, encoding_path

    def test_disabled_security_is_always_authorized(self):
        mgr, _ = self._make_manager(enabled=False)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        result = mgr.evaluate(frame)
        self.assertTrue(result.is_authorized)
        self.assertIn('User Detected', result.status_text)

    def test_missing_reference_is_unauthorized(self):
        mgr, _ = self._make_manager(enabled=True)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        result = mgr.evaluate(frame)
        self.assertFalse(result.is_authorized)
        self.assertIn('No Authorized Face Registered', result.status_text)

    def test_no_face_detected_is_unauthorized(self):
        mgr, encoding_path = self._make_manager(enabled=True)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        result = mgr.evaluate(frame)
        self.assertFalse(result.is_authorized)
        self.assertIn('No Face Detected', result.status_text)

    def test_authorized_when_similarity_exceeds_threshold(self):
        mgr, encoding_path = self._make_manager(enabled=True, threshold=0.75)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        mgr._detect_face_bbox = MagicMock(return_value=(0, 0, 64, 64))
        mgr._encode_face = MagicMock(return_value=np.array([1.0, 0.0], dtype=np.float32))

        result = mgr.evaluate(frame)
        self.assertTrue(result.is_authorized)
        self.assertIn('User Detected', result.status_text)

    def test_unknown_when_similarity_below_threshold(self):
        mgr, encoding_path = self._make_manager(enabled=True, threshold=0.95)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        mgr._detect_face_bbox = MagicMock(return_value=(0, 0, 64, 64))
        mgr._encode_face = MagicMock(return_value=np.array([0.0, 1.0], dtype=np.float32))

        result = mgr.evaluate(frame)
        self.assertFalse(result.is_authorized)
        self.assertEqual(result.status_text, 'Unknown User X')

    def test_hysteresis_prevents_transient_relock_for_authorized_user(self):
        mgr, encoding_path = self._make_manager(enabled=True, threshold=0.84)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        mgr._detect_face_bbox = MagicMock(return_value=(0, 0, 64, 64))

        # First frame clearly authorizes.
        mgr._encode_face = MagicMock(return_value=np.array([1.0, 0.0], dtype=np.float32))
        first = mgr.evaluate(frame)

        # Next frame dips below unlock threshold but stays above lock threshold.
        mgr._encode_face = MagicMock(return_value=np.array([0.80, 0.60], dtype=np.float32))
        second = mgr.evaluate(frame)

        self.assertTrue(first.is_authorized)
        self.assertTrue(second.is_authorized)
        self.assertIn('User Detected', second.status_text)

    def test_marks_user_away_after_delay(self):
        mgr, encoding_path = self._make_manager(enabled=True, threshold=0.8)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()
        mgr._away_delay_s = 2.0

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        mgr._detect_face_bbox = MagicMock(return_value=None)

        with unittest.mock.patch('core.face_security.time.time', side_effect=[10.0, 12.2]):
            first = mgr.evaluate(frame)
            second = mgr.evaluate(frame)

        self.assertFalse(first.system_paused)
        self.assertTrue(second.system_paused)
        self.assertEqual(second.status_text, 'User Away - System Paused')

    def test_user_returns_after_confirm_window(self):
        mgr, encoding_path = self._make_manager(enabled=True, threshold=0.7)
        with open(encoding_path, 'w', encoding='utf-8') as fh:
            json.dump({'encoding': [1.0, 0.0]}, fh)
        mgr._reference_encoding = mgr._load_reference_from_file()
        mgr._away_delay_s = 0.5
        mgr._return_confirm_s = 0.6

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        mgr._encode_face = MagicMock(return_value=np.array([1.0, 0.0], dtype=np.float32))

        # Become away first.
        mgr._detect_face_bbox = MagicMock(return_value=None)
        with unittest.mock.patch('core.face_security.time.time', side_effect=[10.0, 10.8]):
            mgr.evaluate(frame)
            away_result = mgr.evaluate(frame)
        self.assertTrue(away_result.system_paused)

        # Face reappears and is confirmed after return_confirm_s.
        mgr._detect_face_bbox = MagicMock(return_value=(0, 0, 64, 64))
        with unittest.mock.patch('core.face_security.time.time', side_effect=[11.0, 11.8]):
            first_return = mgr.evaluate(frame)
            confirmed_return = mgr.evaluate(frame)

        self.assertTrue(first_return.system_paused)
        self.assertFalse(confirmed_return.system_paused)
        self.assertTrue(confirmed_return.is_authorized)
        self.assertEqual(confirmed_return.status_text, 'User Detected - System Active')


class TestActivationManagerLock(unittest.TestCase):
    def test_force_inactive_locks_active_state(self):
        manager = ActivationManager()
        manager._state = manager.STATE_ACTIVE
        manager.force_inactive('test lock')
        self.assertEqual(manager.state, manager.STATE_INACTIVE)

    def test_force_active_restores_state(self):
        manager = ActivationManager()
        manager._state = manager.STATE_INACTIVE
        manager.force_active('user returned')
        self.assertEqual(manager.state, manager.STATE_ACTIVE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
