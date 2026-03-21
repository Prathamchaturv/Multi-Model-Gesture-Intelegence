"""Calibration utilities for MMGI Phase 2."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Iterable


@dataclass
class CalibrationProfile:
    """Runtime-tunable calibration values."""

    base_cursor_sensitivity: float = 1.0
    min_cursor_sensitivity: float = 0.6
    max_cursor_sensitivity: float = 1.8
    near_hand_distance: float = 0.22
    far_hand_distance: float = 0.08
    gesture_hold_seconds: float = 1.0
    stability_frames: int = 4
    mode_switch_hold_seconds: float = 1.0
    mode_switch_cooldown_seconds: float = 2.0
    debug_overlay_enabled: bool = False


class CalibrationManager:
    """Loads, stores, and applies calibration policy."""

    WIZARD_STEPS = (
        'Show neutral hand distance to set baseline.',
        'Move hand closer for near-range sampling.',
        'Move hand farther for far-range sampling.',
        'Confirm gesture hold and stability preferences.',
    )

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'calibration.json'
        self._config_path = Path(config_path)
        self._profile = CalibrationProfile()
        self._wizard_index = -1
        self._wizard_samples: list[float] = []
        self.load()

    @property
    def profile(self) -> CalibrationProfile:
        return self._profile

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> CalibrationProfile:
        if not self._config_path.exists():
            return self._profile
        try:
            with open(self._config_path, 'r', encoding='utf-8') as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                self._profile = CalibrationProfile(**{**asdict(self._profile), **raw})
        except Exception:
            pass
        return self._profile

    def save(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as fh:
            json.dump(asdict(self._profile), fh, indent=2)

    def update(self, **values) -> CalibrationProfile:
        current = asdict(self._profile)
        current.update(values)
        current['base_cursor_sensitivity'] = float(max(0.2, min(3.0, current['base_cursor_sensitivity'])))
        current['min_cursor_sensitivity'] = float(max(0.1, min(2.5, current['min_cursor_sensitivity'])))
        current['max_cursor_sensitivity'] = float(max(current['min_cursor_sensitivity'], min(3.0, current['max_cursor_sensitivity'])))
        current['gesture_hold_seconds'] = float(max(0.3, min(3.0, current['gesture_hold_seconds'])))
        current['mode_switch_hold_seconds'] = float(max(0.3, min(3.0, current['mode_switch_hold_seconds'])))
        current['mode_switch_cooldown_seconds'] = float(max(0.2, min(5.0, current['mode_switch_cooldown_seconds'])))
        current['stability_frames'] = int(max(2, min(30, current['stability_frames'])))
        current['near_hand_distance'] = float(max(0.05, min(0.5, current['near_hand_distance'])))
        current['far_hand_distance'] = float(max(0.03, min(current['near_hand_distance'] - 0.01, current['far_hand_distance'])))
        self._profile = CalibrationProfile(**current)
        return self._profile

    @staticmethod
    def estimate_hand_distance(landmarks: Iterable[tuple[float, float, float]] | None) -> float | None:
        if not landmarks:
            return None
        points = list(landmarks)
        if len(points) <= 9:
            return None
        wrist = points[0]
        middle_mcp = points[9]
        dx = float(wrist[0]) - float(middle_mcp[0])
        dy = float(wrist[1]) - float(middle_mcp[1])
        dz = float(wrist[2]) - float(middle_mcp[2])
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def cursor_sensitivity_for_distance(self, hand_distance: float | None) -> float:
        profile = self._profile
        if hand_distance is None:
            return profile.base_cursor_sensitivity

        near = profile.near_hand_distance
        far = profile.far_hand_distance
        if near <= far:
            return profile.base_cursor_sensitivity

        ratio = (hand_distance - far) / (near - far)
        ratio = max(0.0, min(1.0, ratio))
        dynamic = profile.min_cursor_sensitivity + ratio * (profile.max_cursor_sensitivity - profile.min_cursor_sensitivity)
        return float(max(profile.min_cursor_sensitivity, min(profile.max_cursor_sensitivity, dynamic)))

    def start_wizard(self) -> str:
        self._wizard_index = 0
        self._wizard_samples = []
        return self.WIZARD_STEPS[self._wizard_index]

    def wizard_record_sample(self, hand_distance: float | None) -> str:
        if self._wizard_index < 0:
            return 'Wizard not active.'
        if hand_distance is not None:
            self._wizard_samples.append(float(hand_distance))

        self._wizard_index += 1
        if self._wizard_index >= len(self.WIZARD_STEPS):
            if self._wizard_samples:
                avg = sum(self._wizard_samples) / len(self._wizard_samples)
                self.update(
                    near_hand_distance=max(0.08, min(0.45, avg * 1.15)),
                    far_hand_distance=max(0.04, min(0.25, avg * 0.75)),
                )
            self._wizard_index = -1
            self._wizard_samples = []
            self.save()
            return 'Calibration wizard complete and saved.'

        return self.WIZARD_STEPS[self._wizard_index]
