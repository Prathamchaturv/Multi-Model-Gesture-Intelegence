"""
Adaptive gesture learning and matching utilities.

Provides:
- position/scale-invariant landmark normalization
- multi-frame gesture recording and averaging
- persistent storage in config/custom_gestures.json
- real-time distance-based matching with configurable threshold
- multi-frame confirmation for stable detections
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


EPS = 1e-6


@dataclass(frozen=True)
class CustomGestureMatch:
    """Represents a successful gesture match."""

    name: str
    action: str
    distance: float


class GestureDataError(ValueError):
    """Raised when gesture landmark data is invalid."""


def normalize_landmarks(landmarks: list[tuple[float, float, float]] | list[list[float]]) -> list[list[float]]:
    """
    Normalize 21 hand landmarks to be translation and scale invariant.

    Steps:
    1. Translate all points relative to wrist (landmark 0).
    2. Scale by the max distance-from-wrist among all points.
    """
    if not landmarks or len(landmarks) != 21:
        raise GestureDataError('Expected exactly 21 landmarks.')

    arr = np.asarray(landmarks, dtype=np.float32)
    if arr.shape != (21, 3):
        raise GestureDataError('Landmarks must have shape (21, 3).')

    wrist = arr[0].copy()
    rel = arr - wrist

    dists = np.linalg.norm(rel, axis=1)
    scale = float(np.max(dists))
    if scale <= EPS:
        raise GestureDataError('Invalid landmark scale; hand appears degenerate.')

    normalized = rel / scale
    return normalized.tolist()


def average_normalized_patterns(patterns: list[list[list[float]]]) -> list[list[float]]:
    """Return the per-landmark mean pattern from normalized gesture frames."""
    if not patterns:
        raise GestureDataError('No patterns provided for averaging.')

    arr = np.asarray(patterns, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[1:] != (21, 3):
        raise GestureDataError('Expected patterns shape (N, 21, 3).')

    avg = np.mean(arr, axis=0)
    return avg.tolist()


class GestureRecorder:
    """Collects valid normalized gesture frames and computes an average pattern."""

    def __init__(self, target_frames: int = 25) -> None:
        self.target_frames = max(5, int(target_frames))
        self._frames: list[list[list[float]]] = []

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def is_complete(self) -> bool:
        return self.frame_count >= self.target_frames

    def reset(self) -> None:
        self._frames.clear()

    def add_frame(self, landmarks: list[tuple[float, float, float]] | list[list[float]] | None) -> bool:
        """
        Add one training frame if valid.

        Returns True only when a valid hand frame was stored.
        """
        if landmarks is None:
            return False

        try:
            norm = normalize_landmarks(landmarks)
        except GestureDataError:
            return False

        self._frames.append(norm)
        return True

    def average_pattern(self) -> list[list[float]]:
        if not self._frames:
            raise GestureDataError('No valid frames recorded.')
        return average_normalized_patterns(self._frames)


class CustomGestureStore:
    """Persistent storage for custom gesture definitions."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self._gestures: dict[str, dict[str, Any]] = {}
        self._last_signature: tuple[int, int] | None = None
        self.load()

    @property
    def gestures(self) -> dict[str, dict[str, Any]]:
        return self._gestures

    def list_gestures(self) -> list[dict[str, Any]]:
        return [
            {
                'name': name,
                'action': data['action'],
                'mode': data.get('mode', 'App Mode'),
                'pattern': data['pattern'],
            }
            for name, data in sorted(self._gestures.items(), key=lambda item: item[0].lower())
        ]

    def add_or_update(
        self,
        name: str,
        normalized_pattern: list[list[float]],
        action: str,
        mode: str = 'App Mode',
    ) -> None:
        clean_name = (name or '').strip()
        clean_action = (action or '').strip()
        clean_mode = (mode or '').strip() or 'App Mode'
        valid_modes = {'App Mode', 'Media Mode', 'System Mode'}
        if not clean_name:
            raise GestureDataError('Gesture name cannot be empty.')
        if not clean_action:
            raise GestureDataError('Gesture action cannot be empty.')
        if clean_mode not in valid_modes:
            raise GestureDataError(f'Invalid gesture mode: {clean_mode}')

        pattern_arr = np.asarray(normalized_pattern, dtype=np.float32)
        if pattern_arr.shape != (21, 3):
            raise GestureDataError('Normalized pattern must have shape (21, 3).')

        self._gestures[clean_name] = {
            'action': clean_action,
            'mode': clean_mode,
            'pattern': pattern_arr.tolist(),
        }
        self.save()

    def delete(self, name: str) -> bool:
        if name in self._gestures:
            del self._gestures[name]
            self.save()
            return True
        return False

    def load(self) -> None:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._gestures = {}
            self.save()
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception:
            self._gestures = {}
            return

        raw_gestures = data.get('gestures', []) if isinstance(data, dict) else []
        loaded: dict[str, dict[str, Any]] = {}

        for item in raw_gestures:
            try:
                name = str(item['name']).strip()
                action = str(item['action']).strip()
                mode = str(item.get('mode', 'App Mode')).strip() or 'App Mode'
                pattern = np.asarray(item['pattern'], dtype=np.float32)
                if not name or not action or pattern.shape != (21, 3):
                    continue
                if mode not in {'App Mode', 'Media Mode', 'System Mode'}:
                    mode = 'App Mode'
                loaded[name] = {
                    'action': action,
                    'mode': mode,
                    'pattern': pattern.tolist(),
                }
            except Exception:
                continue

        self._gestures = loaded
        self._last_signature = self._signature()

    def save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'version': 1,
            'gestures': [
                {
                    'name': name,
                    'action': data['action'],
                    'mode': data.get('mode', 'App Mode'),
                    'pattern': data['pattern'],
                }
                for name, data in sorted(self._gestures.items(), key=lambda item: item[0].lower())
            ],
        }
        with open(self.file_path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2)
        self._last_signature = self._signature()

    def reload_if_changed(self) -> None:
        current = self._signature()
        if current != self._last_signature:
            self.load()

    def _signature(self) -> tuple[int, int] | None:
        try:
            st = self.file_path.stat()
            return (st.st_mtime_ns, st.st_size)
        except Exception:
            return None


class AdaptiveGestureMatcher:
    """Distance-based matcher for custom gestures."""

    def __init__(self, store: CustomGestureStore, threshold: float = 0.12) -> None:
        self.store = store
        self.threshold = float(threshold)

    def match(self, landmarks: list[tuple[float, float, float]] | list[list[float]] | None) -> CustomGestureMatch | None:
        if landmarks is None:
            return None

        self.store.reload_if_changed()

        try:
            current = np.asarray(normalize_landmarks(landmarks), dtype=np.float32)
        except GestureDataError:
            return None

        best: CustomGestureMatch | None = None

        for name, data in self.store.gestures.items():
            pattern = np.asarray(data['pattern'], dtype=np.float32)
            if pattern.shape != (21, 3):
                continue

            # Mean Euclidean distance over all 21 landmarks.
            dist = float(np.linalg.norm(current - pattern, axis=1).mean())
            if dist <= self.threshold:
                if best is None or dist < best.distance:
                    best = CustomGestureMatch(name=name, action=data['action'], distance=dist)

        return best


class MultiFrameGestureConfirmation:
    """Confirms a gesture only if it repeats consistently across several frames."""

    def __init__(self, confirm_frames: int = 4) -> None:
        self.confirm_frames = max(2, int(confirm_frames))
        self._candidate_name: str | None = None
        self._candidate_count: int = 0

    def reset(self) -> None:
        self._candidate_name = None
        self._candidate_count = 0

    def update(self, candidate_name: str | None) -> str | None:
        if not candidate_name:
            self.reset()
            return None

        if candidate_name != self._candidate_name:
            self._candidate_name = candidate_name
            self._candidate_count = 1
            return None

        self._candidate_count += 1
        if self._candidate_count >= self.confirm_frames:
            return self._candidate_name
        return None
