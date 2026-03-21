"""Tests for the runtime multimodal fusion layer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.multimodal_fusion import MultimodalFusionLayer  # noqa: E402
from engine.unified_pipeline import InputEventNormalizer  # noqa: E402


def test_voice_priority_suppresses_gesture_when_both_present() -> None:
    fusion = MultimodalFusionLayer()
    gesture = InputEventNormalizer.from_gesture('Two Fingers', confidence=0.9, timestamp=100.0)
    voice = InputEventNormalizer.from_voice('volume_down', timestamp=100.01)

    events = fusion.merge(
        gesture_event=gesture,
        voice_event=voice,
        gesture_is_stable=True,
        uncertainty_lock_active=False,
    )

    assert len(events) == 1
    assert events[0].type == 'voice'


def test_uncertainty_lock_drops_gesture_input() -> None:
    fusion = MultimodalFusionLayer()
    gesture = InputEventNormalizer.from_gesture('Thumbs Up', confidence=0.95, timestamp=200.0)

    events = fusion.merge(
        gesture_event=gesture,
        voice_event=None,
        gesture_is_stable=True,
        uncertainty_lock_active=True,
    )

    assert events == []


def test_gesture_passes_when_voice_absent_and_stable() -> None:
    fusion = MultimodalFusionLayer()
    gesture = InputEventNormalizer.from_gesture('One Finger', confidence=0.93, timestamp=300.0)

    events = fusion.merge(
        gesture_event=gesture,
        voice_event=None,
        gesture_is_stable=True,
        uncertainty_lock_active=False,
    )

    assert len(events) == 1
    assert events[0].type == 'gesture'
