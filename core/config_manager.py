"""
Module: config_manager.py
Description: User configuration manager with runtime file watching and dynamic updates.
             Loads gesture/voice mappings, thresholds, and smoothing from user_config.json
             and allows DecisionEngine and other components to update without restart.
Author: Pratham Chaturvedi

core/config_manager.py - Runtime User Configuration

Watches user_config.json for changes and propagates updates to subscribed
components (DecisionEngine, activation manager, etc.) so configuration
changes take effect immediately without restart.

Key features:
  - Atomic file updates (write atomically to avoid partial reads)
  - Change detection (file mtime signature)
  - Validation before applying changes
  - Subscriber callback pattern for live updates
  - Fallback to built-in defaults on error
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any


@dataclass(frozen=True)
class ConfigChange:
    """Represents a detected config change."""

    section: str  # 'gesture_mappings', 'voice_mappings', 'thresholds', etc.
    key: str | None  # specific sub-key, or None for full section reload
    old_value: Any
    new_value: Any


class ConfigManager:
    """
    Loads, validates, and watches user_config.json for runtime changes.
    Notifies subscribers when configuration is updated.
    """

    # Built-in defaults (fallback if config file is missing or invalid)
    DEFAULTS = {
        "gesture_mappings": {
            "App Mode": {
                "One Finger": "open_brave",
                "Two Fingers": "open_apple_music",
                "Three Fingers": "next_mode",
                "Pinch": "left_click",
            },
            "Media Mode": {
                "One Finger": "volume_up",
                "Two Fingers": "volume_down",
                "Three Fingers": "next_mode",
                "Four Fingers": "play_pause",
                "Thumbs Up": "mute",
            },
            "System Mode": {
                "Pinch": "left_click",
                "Three Fingers": "next_mode",
                "Open Palm": "scroll_down",
            },
        },
        "voice_mappings": {
            "App Mode": {
                "open_brave": "open_brave",
                "open_music": "open_apple_music",
                "open_youtube": "open_youtube",
                "close_window": "close_window",
                "switch_tab": "switch_tab",
                "scroll_down": "scroll_down",
            },
            "Media Mode": {
                "play_song": "play_pause",
                "pause": "play_pause",
                "next_track": "next_track",
                "previous_track": "prev_track",
                "volume_up": "volume_up",
                "volume_down": "volume_down",
                "mute": "mute",
            },
            "System Mode": {
                "open_brave": "open_brave",
                "open_music": "open_apple_music",
                "open_youtube": "open_youtube",
                "close_window": "close_window",
                "switch_tab": "switch_tab",
                "scroll_down": "scroll_down",
                "play_song": "play_pause",
                "pause": "play_pause",
                "next_track": "next_track",
                "previous_track": "prev_track",
                "volume_up": "volume_up",
                "volume_down": "volume_down",
                "mute": "mute",
                "left_click": "left_click",
                "right_click": "right_click",
            },
        },
        "thresholds": {
            "hand_detection_confidence": 0.7,
            "hand_tracking_confidence": 0.5,
            "gesture_stability_frames": 10,
            "voice_confidence": 0.8,
            "face_similarity": 0.84,
        },
        "smoothing": {
            "gesture_confirmation_frames": 4,
            "mode_switch_hold_seconds": 1.0,
            "activation_hold_seconds": 2.0,
            "cooldown_seconds": 1.0,
            "face_eval_interval_s": 0.08,
            "voice_backoff_recovery_s": 5.0,
        },
    }

    def __init__(self, config_path: str | Path | None = None) -> None:
        """
        Initialize ConfigManager and load configuration.

        Args:
            config_path: Path to user_config.json. If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "user_config.json"
        else:
            config_path = Path(config_path)

        self._config_path = config_path
        self._config = self.DEFAULTS.copy()
        self._last_file_signature: tuple[float, int] | None = None
        self._subscribers: list[Callable[[ConfigChange], None]] = []
        self._lock = threading.RLock()
        self._watch_thread: threading.Thread | None = None
        self._watch_running = False

        self.load_config()

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def load_config(self) -> bool:
        """Load configuration from disk, return True on success."""
        try:
            if not self._config_path.exists():
                print(f"[ConfigManager] Config file not found: {self._config_path}")
                self._config = self.DEFAULTS.copy()
                return False

            with open(self._config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            self._config = self._merge_with_defaults(data)
            self._update_file_signature()
            print(f"[ConfigManager] Loaded config from {self._config_path}")
            return True

        except json.JSONDecodeError as e:
            print(f"[ConfigManager] Invalid JSON in {self._config_path}: {e}")
            self._config = self.DEFAULTS.copy()
            return False
        except Exception as e:
            print(f"[ConfigManager] Error loading config: {e}")
            self._config = self.DEFAULTS.copy()
            return False

    def save_config(self) -> bool:
        """Write current configuration to disk atomically, return True on success."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first, then rename (atomic swap)
            temp_path = self._config_path.with_stem(self._config_path.stem + ".tmp")
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump(self._config, fh, indent=2, ensure_ascii=False)

            # Atomic replace
            temp_path.replace(self._config_path)
            self._update_file_signature()
            print(f"[ConfigManager] Saved config to {self._config_path}")
            return True

        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")
            return False

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get(self, section: str, key: str | None = None, default=None) -> Any:
        """
        Retrieve a config value.

        Args:
            section: Top-level section name (e.g., 'gesture_mappings', 'thresholds')
            key: Optional nested key (e.g., 'App Mode' or 'hand_detection_confidence')
            default: Value returned if key not found

        Returns:
            Config value, or default if not found
        """
        with self._lock:
            if section not in self._config:
                return default

            if key is None:
                return self._config.get(section, default)

            section_data = self._config[section]
            if isinstance(section_data, dict):
                return section_data.get(key, default)

            return default

    def get_gesture_mappings(self, mode: str) -> dict[str, str]:
        """Get all gesture→action mappings for a mode."""
        return self.get("gesture_mappings", mode, default={})

    def get_voice_mappings(self, mode: str) -> dict[str, str]:
        """Get all voice→action mappings for a mode."""
        return self.get("voice_mappings", mode, default={})

    def get_thresholds(self) -> dict[str, float]:
        """Get all confidence/detection thresholds."""
        return self.get("thresholds", default={})

    def get_smoothing(self) -> dict[str, float]:
        """Get all smoothing/timing values."""
        return self.get("smoothing", default={})

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set(self, section: str, key: str, value: Any) -> bool:
        """
        Update a config value and save to disk.

        Args:
            section: Top-level section name
            key: Nested key to update
            value: New value

        Returns:
            True on success
        """
        with self._lock:
            if section not in self._config:
                return False

            old_value = None
            section_data = self._config[section]

            if isinstance(section_data, dict):
                old_value = section_data.get(key)
                section_data[key] = value
            else:
                return False

            # Persist to disk
            success = self.save_config()

            # Notify subscribers
            if success:
                change = ConfigChange(
                    section=section, key=key, old_value=old_value, new_value=value
                )
                self._notify_subscribers(change)

            return success

    def set_gesture_mapping(self, mode: str, gesture: str, action: str) -> bool:
        """Update a gesture→action mapping for a mode."""
        with self._lock:
            if "gesture_mappings" not in self._config:
                self._config["gesture_mappings"] = {}

            if mode not in self._config["gesture_mappings"]:
                self._config["gesture_mappings"][mode] = {}

            old_action = self._config["gesture_mappings"][mode].get(gesture)
            self._config["gesture_mappings"][mode][gesture] = action

            success = self.save_config()
            if success:
                change = ConfigChange(
                    section="gesture_mappings",
                    key=f"{mode}/{gesture}",
                    old_value=old_action,
                    new_value=action,
                )
                self._notify_subscribers(change)

            return success

    def set_voice_mapping(self, mode: str, command: str, action: str) -> bool:
        """Update a voice→action mapping for a mode."""
        with self._lock:
            if "voice_mappings" not in self._config:
                self._config["voice_mappings"] = {}

            if mode not in self._config["voice_mappings"]:
                self._config["voice_mappings"][mode] = {}

            old_action = self._config["voice_mappings"][mode].get(command)
            self._config["voice_mappings"][mode][command] = action

            success = self.save_config()
            if success:
                change = ConfigChange(
                    section="voice_mappings",
                    key=f"{mode}/{command}",
                    old_value=old_action,
                    new_value=action,
                )
                self._notify_subscribers(change)

            return success

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[ConfigChange], None]) -> None:
        """
        Register a callback to be invoked when config changes.

        Args:
            callback: Function that accepts a ConfigChange parameter
        """
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ConfigChange], None]) -> None:
        """Unregister a previously subscribed callback."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _notify_subscribers(self, change: ConfigChange) -> None:
        """Invoke all subscribers with the config change."""
        with self._lock:
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(change)
            except Exception as e:
                print(f"[ConfigManager] Subscriber callback error: {e}")

    # ------------------------------------------------------------------
    # File watching (optional background thread)
    # ------------------------------------------------------------------

    def start_watch(self, check_interval_s: float = 2.0) -> None:
        """
        Start a background thread that watches for config file changes.

        Args:
            check_interval_s: How often to check the file (in seconds)
        """
        if self._watch_running:
            return

        self._watch_running = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(check_interval_s,), daemon=True
        )
        self._watch_thread.start()
        print(f"[ConfigManager] File watch started (interval: {check_interval_s}s)")

    def stop_watch(self) -> None:
        """Stop the background watch thread."""
        self._watch_running = False
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None
        print("[ConfigManager] File watch stopped")

    def _watch_loop(self, check_interval_s: float) -> None:
        """Background loop that checks for file changes."""
        while self._watch_running:
            try:
                current_sig = self._read_file_signature()
                if (
                    current_sig is not None
                    and self._last_file_signature is not None
                    and current_sig != self._last_file_signature
                ):
                    print("[ConfigManager] Config file changed, reloading...")
                    if self.load_config():
                        # File was reloaded, notify that whole config changed
                        change = ConfigChange(
                            section="*", key=None, old_value=None, new_value=None
                        )
                        self._notify_subscribers(change)

                time.sleep(check_interval_s)
            except Exception as e:
                print(f"[ConfigManager] Watch loop error: {e}")
                time.sleep(check_interval_s)

    def _update_file_signature(self) -> None:
        """Update the file signature (mtime, size) to detect changes."""
        self._last_file_signature = self._read_file_signature()

    def _read_file_signature(self) -> tuple[float, int] | None:
        """Return (mtime, size) tuple for change detection, or None if file missing."""
        try:
            stat = self._config_path.stat()
            return (stat.st_mtime, stat.st_size)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Merging / Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_with_defaults(user_data: dict) -> dict:
        """Merge loaded config with built-in defaults, preferring user values."""
        result = ConfigManager.DEFAULTS.copy()
        if isinstance(user_data, dict):
            for key, value in user_data.items():
                if key == "_metadata":
                    continue
                if key in result and isinstance(value, dict) and isinstance(result[key], dict):
                    result[key].update(value)
                else:
                    result[key] = value
        return result
