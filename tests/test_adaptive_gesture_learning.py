"""Tests for adaptive gesture learning and matching."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from core.adaptive_gesture_learning import (
    AdaptiveGestureMatcher,
    CustomGestureStore,
    GestureDataError,
    GestureRecorder,
    MultiFrameGestureConfirmation,
    average_normalized_patterns,
    normalize_landmarks,
)


def _make_landmarks(scale: float = 1.0, shift: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> list[list[float]]:
    pts = []
    sx, sy, sz = shift
    for i in range(21):
        pts.append([
            sx + (i * 0.01 * scale),
            sy + (i * 0.015 * scale),
            sz + (i * 0.002 * scale),
        ])
    return pts


def test_normalize_landmarks_is_translation_and_scale_invariant() -> None:
    base = _make_landmarks(scale=1.0, shift=(0.0, 0.0, 0.0))
    moved_scaled = _make_landmarks(scale=2.5, shift=(0.7, -1.1, 0.4))

    n1 = np.asarray(normalize_landmarks(base), dtype=np.float32)
    n2 = np.asarray(normalize_landmarks(moved_scaled), dtype=np.float32)

    assert np.allclose(n1, n2, atol=1e-5)


def test_average_pattern_shape() -> None:
    pattern_a = normalize_landmarks(_make_landmarks())
    pattern_b = normalize_landmarks(_make_landmarks(scale=1.1, shift=(0.02, 0.01, -0.02)))

    avg = average_normalized_patterns([pattern_a, pattern_b])
    arr = np.asarray(avg, dtype=np.float32)
    assert arr.shape == (21, 3)


def test_recorder_skips_invalid_frames_and_collects_valid() -> None:
    rec = GestureRecorder(target_frames=6)
    assert rec.add_frame(None) is False
    assert rec.frame_count == 0

    valid = _make_landmarks()
    for _ in range(6):
        assert rec.add_frame(valid) is True

    assert rec.is_complete
    avg = rec.average_pattern()
    assert np.asarray(avg, dtype=np.float32).shape == (21, 3)


def test_store_persists_and_reloads_gesture() -> None:
    with tempfile.TemporaryDirectory() as td:
        store_path = Path(td) / 'custom_gestures.json'
        store = CustomGestureStore(store_path)

        pattern = normalize_landmarks(_make_landmarks())
        store.add_or_update('WaveCustom', pattern, 'volume_up')

        reloaded = CustomGestureStore(store_path)
        items = reloaded.list_gestures()
        assert len(items) == 1
        assert items[0]['name'] == 'WaveCustom'
        assert items[0]['action'] == 'volume_up'
        assert items[0]['mode'] == 'App Mode'


def test_store_persists_and_reloads_mode() -> None:
    with tempfile.TemporaryDirectory() as td:
        store_path = Path(td) / 'custom_gestures.json'
        store = CustomGestureStore(store_path)

        pattern = normalize_landmarks(_make_landmarks())
        store.add_or_update('ModeSpecific', pattern, 'open_youtube', mode='Media Mode')

        reloaded = CustomGestureStore(store_path)
        items = reloaded.list_gestures()
        assert len(items) == 1
        assert items[0]['name'] == 'ModeSpecific'
        assert items[0]['action'] == 'open_youtube'
        assert items[0]['mode'] == 'Media Mode'


def test_matcher_returns_best_match_under_threshold() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = CustomGestureStore(Path(td) / 'custom_gestures.json')
        pattern = normalize_landmarks(_make_landmarks())
        store.add_or_update('MyPose', pattern, 'mute')

        matcher = AdaptiveGestureMatcher(store=store, threshold=0.03)
        matched = matcher.match(_make_landmarks(scale=1.3, shift=(0.2, -0.3, 0.1)))

        assert matched is not None
        assert matched.name == 'MyPose'
        assert matched.action == 'mute'


def test_matcher_returns_none_when_above_threshold() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = CustomGestureStore(Path(td) / 'custom_gestures.json')
        pattern = normalize_landmarks(_make_landmarks())
        store.add_or_update('CloseFistCustom', pattern, 'play_pause')

        matcher = AdaptiveGestureMatcher(store=store, threshold=0.00001)
        distorted = _make_landmarks()
        distorted[8][0] += 0.25
        distorted[12][1] -= 0.30
        distorted[16][2] += 0.18
        matched = matcher.match(distorted)
        assert matched is None


def test_confirmation_requires_multiple_frames() -> None:
    conf = MultiFrameGestureConfirmation(confirm_frames=3)
    assert conf.update('A') is None
    assert conf.update('A') is None
    assert conf.update('A') == 'A'
    assert conf.update(None) is None


def test_normalize_rejects_invalid_landmark_count() -> None:
    bad = [[0.0, 0.0, 0.0] for _ in range(20)]
    try:
        normalize_landmarks(bad)
        raise AssertionError('Expected GestureDataError')
    except GestureDataError:
        pass
