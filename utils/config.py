"""
Module: config.py
Description: Dot-key configuration loader — reads JSON config files and merges
             them with built-in defaults, exposing values via attribute access.
Author: Pratham Chaturvedi

utils/config.py - Settings Manager

Loads configuration from JSON files and provides defaults.
Centralises all configurable parameters for the MMGI system.
"""

import json
from pathlib import Path


class Config:
    """Centralised configuration manager with sensible defaults."""

    _DEFAULTS = {
        'camera': {
            'width': 1280,
            'height': 720,
            'fps': 30,
        },
        'hand_tracking': {
            'max_num_hands': 2,
            'min_detection_confidence': 0.7,
            'min_tracking_confidence': 0.5,
        },
        'activation': {
            'open_palm_duration': 2.0,
            'cooldown_duration': 1.0,
            'stability_threshold': 10,
        },
        'display': {
            'show_landmarks': True,
            'show_gesture': True,
            'show_status': True,
            'show_fps': True,
            'show_finger_states': True,
            'show_action_feedback': True,
            'show_hand_detection': True,
        },
        'apps': {
            'brave_path': r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe',
            'apple_music_aumid': 'AppleInc.AppleMusicWin_nzyj5cx40ttqa!App',
        },
        'adaptive_gesture': {
            'enabled': True,
            'training_frames': 25,
            'match_threshold': 0.12,
            'confirm_frames': 4,
            'store_path': 'config/custom_gestures.json',
        },
    }

    def __init__(self, config_path: str | None = None):
        self._flat: dict = {}
        self._flatten(self._DEFAULTS, '', self._flat)

        if config_path is not None:
            self._load_file(Path(config_path))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        """Return value for a dot-separated key, e.g. 'camera.width'."""
        return self._flat.get(key, default)

    def set(self, key: str, value) -> None:
        """Override a setting at runtime."""
        self._flat[key] = value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(nested: dict, prefix: str, result: dict) -> None:
        """Recursively flatten a nested dict to dot-separated keys."""
        for k, v in nested.items():
            full_key = f'{prefix}.{k}' if prefix else k
            if isinstance(v, dict):
                Config._flatten(v, full_key, result)
            else:
                result[full_key] = v

    def _load_file(self, path: Path) -> None:
        """Merge settings from a JSON file (overrides defaults)."""
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            self._flatten(data, '', self._flat)
            print(f'[Config] Loaded settings from {path}')
        except FileNotFoundError:
            print(f'[Config] Config file not found: {path} — using defaults')
        except json.JSONDecodeError as exc:
            print(f'[Config] Invalid JSON in {path}: {exc} — using defaults')
        except Exception as exc:
            print(f'[Config] Warning: could not load {path}: {exc}')
