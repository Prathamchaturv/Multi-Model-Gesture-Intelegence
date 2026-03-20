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
        self.assertIn('User Recognized', result.status_text)

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
        self.assertIn('User Recognized', result.status_text)

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


class TestActivationManagerLock(unittest.TestCase):
    def test_force_inactive_locks_active_state(self):
        manager = ActivationManager()
        manager._state = manager.STATE_ACTIVE
        manager.force_inactive('test lock')
        self.assertEqual(manager.state, manager.STATE_INACTIVE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
