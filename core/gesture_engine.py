"""Compatibility facade for gesture processing engine."""

from core.gesture_classifier import GestureClassifier, classify_gesture

__all__ = [
    'GestureClassifier',
    'classify_gesture',
]
