"""
tests/test_gesture_classifier.py - Unit tests for GestureClassifier

Run:
    python -m pytest tests/test_gesture_classifier.py -v
    # or
    python tests/test_gesture_classifier.py
"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from core.gesture_classifier import GestureClassifier


class TestGestureClassifier(unittest.TestCase):
    """Tests for rule-based gesture classification."""

    def setUp(self) -> None:
        self.clf = GestureClassifier()

    # ------------------------------------------------------------------
    # Named gestures
    # ------------------------------------------------------------------

    def test_open_palm(self) -> None:
        states = {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': True}
        self.assertEqual(self.clf.classify(states), 'Open Palm')

    def test_fist(self) -> None:
        states = {'thumb': False, 'index': False, 'middle': False, 'ring': False, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Fist')

    def test_thumbs_up(self) -> None:
        states = {'thumb': True, 'index': False, 'middle': False, 'ring': False, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Thumbs Up')

    def test_one_finger(self) -> None:
        states = {'thumb': False, 'index': True, 'middle': False, 'ring': False, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'One Finger')

    def test_two_fingers(self) -> None:
        states = {'thumb': False, 'index': True, 'middle': True, 'ring': False, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Two Fingers')

    def test_three_fingers(self) -> None:
        states = {'thumb': False, 'index': True, 'middle': True, 'ring': True, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Three Fingers')

    def test_four_fingers(self) -> None:
        states = {'thumb': False, 'index': True, 'middle': True, 'ring': True, 'pinky': True}
        self.assertEqual(self.clf.classify(states), 'Four Fingers')

    def test_pinky(self) -> None:
        states = {'thumb': False, 'index': False, 'middle': False, 'ring': False, 'pinky': True}
        self.assertEqual(self.clf.classify(states), 'Pinky')

    def test_thumb_index_middle_and_ring(self) -> None:
        states = {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Thumb, Index, Middle and Ring')

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_unknown_returns_unknown(self) -> None:
        # Thumb + index + ring only — does not match any defined pattern
        states = {'thumb': True, 'index': True, 'middle': False, 'ring': True, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Unknown')

    def test_empty_states_returns_unknown(self) -> None:
        self.assertEqual(self.clf.classify({}), 'Unknown')

    def test_none_states_returns_unknown(self) -> None:
        self.assertEqual(self.clf.classify(None), 'Unknown')

    def test_partial_states_still_matches(self) -> None:
        # Three Fingers pattern only checks index/middle/ring/pinky (not thumb)
        states = {'index': True, 'middle': True, 'ring': True, 'pinky': False}
        self.assertEqual(self.clf.classify(states), 'Three Fingers')

    # ------------------------------------------------------------------
    # Consistency
    # ------------------------------------------------------------------

    def test_all_named_gestures_are_classified(self) -> None:
        """Each named pattern should classify without returning Unknown."""
        expected_patterns: list[tuple[str, dict]] = [
            ('Open Palm',      {'thumb': True,  'index': True,  'middle': True,  'ring': True,  'pinky': True}),
            ('Fist',           {'thumb': False, 'index': False, 'middle': False, 'ring': False, 'pinky': False}),
            ('Thumbs Up',      {'thumb': True,  'index': False, 'middle': False, 'ring': False, 'pinky': False}),
            ('One Finger',     {'index': True,  'middle': False, 'ring': False, 'pinky': False}),
            ('Two Fingers',    {'index': True,  'middle': True,  'ring': False, 'pinky': False}),
            ('Three Fingers',  {'index': True,  'middle': True,  'ring': True,  'pinky': False}),
            ('Four Fingers',   {'index': True,  'middle': True,  'ring': True,  'pinky': True}),
            ('Pinky',          {'index': False, 'middle': False, 'ring': False, 'pinky': True}),
            ('Thumb, Index, Middle and Ring', {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': False}),
        ]
        for name, states in expected_patterns:
            with self.subTest(gesture=name):
                result = self.clf.classify(states)
                self.assertEqual(result, name, f'Expected {name}, got {result} for states {states}')


if __name__ == '__main__':
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# Simple function-style tests (Phase 3 style)
# ---------------------------------------------------------------------------

from core.gesture_classifier import classify_gesture  # noqa: E402


def test_open_palm():
    fingers = [1, 1, 1, 1, 1]   # all extended
    assert classify_gesture(fingers) == 'Open Palm'


def test_fist():
    fingers = [0, 0, 0, 0, 0]   # all curled
    assert classify_gesture(fingers) == 'Fist'


def test_thumbs_up():
    fingers = [1, 0, 0, 0, 0]   # only thumb up
    assert classify_gesture(fingers) == 'Thumbs Up'


def test_one_finger():
    fingers = [0, 1, 0, 0, 0]   # only index up
    assert classify_gesture(fingers) == 'One Finger'


def test_two_fingers():
    fingers = [0, 1, 1, 0, 0]   # index + middle
    assert classify_gesture(fingers) == 'Two Fingers'


def test_classify_gesture_accepts_dict():
    states = {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': False}
    assert classify_gesture(states) == 'Thumb, Index, Middle and Ring'
