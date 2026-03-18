"""
Module: decision_engine.py
Description: Smart Mode state machine — manages the 3-mode cycle
             (App / Media / System), resolves gestures to action strings,
             and enforces the stability-gate hold for mode switching.
Author: Pratham Chaturvedi

engine/decision_engine.py - Smart Mode Decision Engine

Implements a 3-mode (App / Media / System) gesture action resolver.

Mode Switching
--------------
Hold Three Fingers for 1 second → cycles  App → Media → System → App
(10-frame stability + 1.5 s cooldown before next switch)

One Finger and Two Fingers are now **free action gestures** in each mode
and will never be intercepted as mode-switch triggers.

Mode Action Mappings (from gesture_map.json)
--------------------------------------------
App Mode    : One Finger → open_brave | Two Fingers → open_apple_music
Media Mode  : One Finger → volume_up | Two Fingers → volume_down
              Four Fingers → play_pause | Thumbs Up → mute
System Mode : (empty — to be configured)
"""

import json
import time
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODES            = ('App Mode', 'Media Mode', 'System Mode')
DEFAULT_MODE     = 'App Mode'
STABILITY_FRAMES = 10          # consecutive frames same gesture required
HOLD_SECONDS     = 1.0         # seconds the gesture must be held
COOLDOWN_SECONDS = 1.5         # seconds before next mode switch allowed

# Whitelist of action strings that may appear in gesture_map.json.
# Any action not in this set will be rejected during config loading.
ALLOWED_ACTIONS: frozenset[str] = frozenset({
    # Application launchers
    'open_brave',
    'open_apple_music',
    # Generic aliases accepted from external configs
    'open_browser',
    'open_music',
    # Media controls
    'next_track',
    'prev_track',
    'previous_track',
    'play_pause',
    'pause_media',
    # Volume controls
    'volume_up',
    'volume_down',
    'mute',
    # Mode switching
    'next_mode',
    'switch_mode',
})

# Special sentinel stored in mode_switch map for cycling behaviour
_NEXT_MODE = 'next_mode'


class DecisionEngine:
    """
    Smart Mode gesture-to-action resolver.

    Usage
    -----
    engine = DecisionEngine()
    # Per frame: feed the current gesture, get back (action | None, mode_changed)
    action, mode_changed = engine.process(gesture)
    """

    # Built-in fallback mode maps (used if gesture_map.json is missing)
    _DEFAULT_MAPS: dict[str, dict[str, str]] = {
        'mode_switch': {
            'Three Fingers': 'next_mode',   # hold 1 s → cycle App→Media→System→App
        },
        'App Mode': {
            'One Finger':    'open_brave',
            'Two Fingers':   'open_apple_music',
        },
        'Media Mode': {
            'One Finger':    'volume_up',
            'Two Fingers':   'volume_down',
            'Four Fingers':  'play_pause',
            'Thumbs Up':     'mute',
        },
        'System Mode': {},
    }

    def __init__(self, config_path: str | Path | None = None):
        # Mode maps loaded from JSON
        self._mode_switch_map: dict[str, str]            = {}
        self._action_maps:     dict[str, dict[str, str]] = {}

        # Runtime state
        self.current_mode: str = DEFAULT_MODE

        # Mode-switch stability tracking
        self._candidate_mode:   str | None = None
        self._stable_count:     int        = 0
        self._hold_start:       float      = 0.0
        self._last_switch_time: float      = 0.0

        # Resolve config path
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'gesture_map.json'
        self._config_path = Path(config_path)
        self._last_map_signature: tuple[int, int] | None = None
        self._last_reload_check: float = 0.0
        self._reload_check_interval_seconds: float = 0.2
        self._load_map(self._config_path)

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def process(self, gesture: str | None) -> tuple[str | None, bool]:
        """
        Process one frame's gesture.

        Returns
        -------
        (action, mode_changed)
            action       – action string to execute, or None
            mode_changed – True if the mode just switched this frame
        """
        self._maybe_reload_map()

        if gesture is None:
            self._reset_stability()
            return None, False

        # --- Mode-switch path ---
        if self.is_mode_switch(gesture):
            mode_changed = self._update_mode_stability(gesture)
            return None, mode_changed          # never an action for switch gestures

        # --- Normal action path ---
        self._reset_stability()
        action = self.get_action(gesture, self.current_mode)
        return action, False

    def get_action(self, gesture: str, mode: str | None = None) -> str | None:
        """
        Look up the action for gesture in the given mode (defaults to current_mode).

        Args:
            gesture: Recognised gesture name (e.g. 'Thumbs Up')
            mode:    One of 'App Mode', 'Media Mode', 'System Mode', or None

        Returns:
            Action string or None.
        """
        target_mode = mode if mode is not None else self.current_mode
        return self._action_maps.get(target_mode, {}).get(gesture)

    def is_mode_switch(self, gesture: str) -> bool:
        """Return True if gesture is a mode-switch gesture (1/2/3 fingers)."""
        return gesture in self._mode_switch_map

    def resolve_mode_switch(self, gesture: str) -> str | None:
        """Return target mode for a mode-switch gesture, or None."""
        return self._mode_switch_map.get(gesture)

    @property
    def mode_stability_progress(self) -> float:
        """
        0.0 – 1.0 progress toward triggering a mode switch.
        Combines frame stability and hold time.
        """
        if self._candidate_mode is None:
            return 0.0
        frame_prog = min(self._stable_count / STABILITY_FRAMES, 1.0)
        if self._hold_start > 0:
            time_prog = min((time.time() - self._hold_start) / HOLD_SECONDS, 1.0)
        else:
            time_prog = 0.0
        return (frame_prog * 0.5 + time_prog * 0.5)

    # ------------------------------------------------------------------
    # Mode-switch stability logic (private)
    # ------------------------------------------------------------------

    def _update_mode_stability(self, gesture: str) -> bool:
        """
        Track hold stability for mode-switch gestures.
        Returns True when a mode switch is committed.

        Value 'next_mode' cycles: App Mode → Media Mode → System Mode → App Mode.
        """
        raw_target = self._mode_switch_map.get(gesture)

        now = time.time()

        # Cooldown guard
        if now - self._last_switch_time < COOLDOWN_SECONDS:
            return False

        # Resolve cycling target
        if raw_target == _NEXT_MODE:
            idx = MODES.index(self.current_mode) if self.current_mode in MODES else 0
            target_mode = MODES[(idx + 1) % len(MODES)]
        else:
            target_mode = raw_target

        # Reset if candidate changed
        if target_mode != self._candidate_mode:
            self._candidate_mode = target_mode
            self._stable_count   = 1
            self._hold_start     = now
            return False

        self._stable_count += 1

        # Check both stability AND hold duration
        if (self._stable_count >= STABILITY_FRAMES
                and (now - self._hold_start) >= HOLD_SECONDS):
            old_mode = self.current_mode
            self.current_mode        = target_mode
            self._last_switch_time   = now
            ts = datetime.now().strftime('%H:%M:%S')
            print(f'[DecisionEngine] [{ts}] Mode Changed  {old_mode} → {target_mode}')
            self._reset_stability()
            return True

        return False

    def _reset_stability(self) -> None:
        self._candidate_mode = None
        self._stable_count   = 0
        self._hold_start     = 0.0

    def _maybe_reload_map(self) -> None:
        """Hot-reload gesture_map.json when file signature (mtime + size) changes."""
        now = time.time()
        if now - self._last_reload_check < self._reload_check_interval_seconds:
            return

        self._last_reload_check = now
        current_signature = self._read_map_signature(self._config_path)
        if self._last_map_signature != current_signature:
            self._load_map(self._config_path)

    @staticmethod
    def _read_map_signature(path: Path) -> tuple[int, int] | None:
        """Return a file signature tuple (mtime_ns, size) or None when unavailable."""
        try:
            st = path.stat()
            return (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Config loading (private)
    # ------------------------------------------------------------------

    def _load_map(self, path: Path) -> None:
        """Load Smart Mode mappings from gesture_map.json, rejecting unknown actions."""
        data: dict = {}
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            self._last_map_signature = self._read_map_signature(path)
            print(f'[DecisionEngine] Loaded gesture map from {path}')
        except FileNotFoundError:
            self._last_map_signature = None
            print(f'[DecisionEngine] gesture_map.json not found — using built-in defaults')
        except (json.JSONDecodeError, KeyError) as exc:
            self._last_map_signature = None
            print(f'[DecisionEngine] Warning: could not parse gesture map: {exc} — using defaults')
        except Exception as exc:
            self._last_map_signature = None
            print(f'[DecisionEngine] Warning: {exc} — using defaults')

        defaults = self._DEFAULT_MAPS

        # Validate mode-switch entries from JSON (only 'next_mode'/'switch_mode' allowed)
        raw_switch = data.get('mode_switch', {})
        validated_switch: dict[str, str] = {}
        for gesture, action in raw_switch.items():
            if action in ALLOWED_ACTIONS:
                validated_switch[gesture] = action
            else:
                print(
                    f'[DecisionEngine] Security: rejected invalid mode_switch action '
                    f'"{action}" for gesture "{gesture}"'
                )

        self._mode_switch_map = {**defaults['mode_switch'], **validated_switch}

        # Validate per-mode action entries
        for mode in MODES:
            raw_mode = data.get(mode, {})
            validated_mode: dict[str, str] = {}
            for gesture, action in raw_mode.items():
                if action in ALLOWED_ACTIONS:
                    validated_mode[gesture] = action
                else:
                    print(
                        f'[DecisionEngine] Security: rejected invalid action '
                        f'"{action}" for gesture "{gesture}" in {mode}'
                    )
            self._action_maps[mode] = {**defaults.get(mode, {}), **validated_mode}


# ---------------------------------------------------------------------------
# Module-level convenience wrapper (used by simple tests and external callers)
# ---------------------------------------------------------------------------

_engine = DecisionEngine()


def get_action(mode: str, gesture: str) -> str | None:
    """
    Look up the action string for a gesture in a given mode.

    Args:
        mode:    One of 'App Mode', 'Media Mode', 'System Mode'.
        gesture: Recognised gesture name, e.g. 'Thumbs Up'.

    Returns:
        Action string (e.g. 'play_pause') or None if no mapping exists.
    """
    return _engine.get_action(gesture, mode)
