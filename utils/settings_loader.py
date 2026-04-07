"""Dynamic runtime settings loader for quick tuning without code changes."""

from __future__ import annotations

import json
import time
from pathlib import Path


class RuntimeSettingsLoader:
    """Loads and hot-reloads settings.json using low-overhead mtime checks."""

    _DEFAULTS: dict[str, float] = {
        'gesture_threshold': 0.7,
        'voice_confidence': 0.85,
        'cooldown': 0.25,
        'cursor_sensitivity': 1.0,
    }

    def __init__(self, settings_path: str | Path, poll_interval_s: float = 0.5) -> None:
        self._path = Path(settings_path)
        self._poll_interval_s = max(0.1, float(poll_interval_s))
        self._last_check_ts = 0.0
        self._last_mtime: float | None = None
        self._settings = dict(self._DEFAULTS)
        self._load(force=True)

    def get_settings(self) -> dict[str, float]:
        """Return a copy of the current settings payload."""
        return dict(self._settings)

    def reload_if_changed(self) -> bool:
        """Reload settings when file mtime changes. Returns True when reloaded."""
        now = time.time()
        if (now - self._last_check_ts) < self._poll_interval_s:
            return False
        self._last_check_ts = now
        return self._load(force=False)

    def _load(self, force: bool) -> bool:
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            # Keep defaults when the file is missing.
            return False

        if not force and self._last_mtime is not None and mtime == self._last_mtime:
            return False

        try:
            with open(self._path, 'r', encoding='utf-8') as fh:
                raw = json.load(fh)
        except Exception:
            # Keep the last known good settings on malformed updates.
            return False

        if not isinstance(raw, dict):
            return False

        merged = dict(self._DEFAULTS)
        for key in self._DEFAULTS:
            if key in raw:
                try:
                    merged[key] = float(raw[key])
                except (TypeError, ValueError):
                    continue

        merged['gesture_threshold'] = max(0.0, min(1.0, merged['gesture_threshold']))
        merged['voice_confidence'] = max(0.0, min(1.0, merged['voice_confidence']))
        merged['cooldown'] = max(0.0, merged['cooldown'])
        merged['cursor_sensitivity'] = max(0.1, merged['cursor_sensitivity'])

        self._settings = merged
        self._last_mtime = mtime
        return True
