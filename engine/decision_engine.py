"""Smart mode decision engine with unified gesture and voice resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import time


MODES = ('App Mode', 'Media Mode', 'System Mode')
DEFAULT_MODE = 'App Mode'
STABILITY_FRAMES = 10
HOLD_SECONDS = 1.0
COOLDOWN_SECONDS = 2.0

ALLOWED_ACTIONS: frozenset[str] = frozenset({
    'open_brave',
    'open_apple_music',
    'open_browser',
    'open_music',
    'open_youtube',
    'close_window',
    'switch_tab',
    'scroll_down',
    'left_click',
    'right_click',
    'double_click',
    'next_track',
    'prev_track',
    'previous_track',
    'play_pause',
    'pause_media',
    'volume_up',
    'volume_down',
    'mute',
    'next_mode',
    'switch_mode',
})

_NEXT_MODE = 'next_mode'


@dataclass(frozen=True)
class DecisionOutcome:
    action: str | None = None
    target_mode: str | None = None
    reason: str | None = None


class DecisionEngine:
    """Resolves InputEvents or legacy gesture frames to executable actions."""

    _DEFAULT_MAPS: dict[str, dict] = {
        'mode_switch': {
            'Three Fingers': 'next_mode',
        },
        'voice_mode_switch': {
            'next_mode': 'next_mode',
            'switch_to_app_mode': 'App Mode',
            'switch_to_media_mode': 'Media Mode',
            'switch_to_system_mode': 'System Mode',
        },
        'App Mode': {
            'One Finger': 'open_brave',
            'Two Fingers': 'open_apple_music',
        },
        'Media Mode': {
            'One Finger': 'volume_up',
            'Two Fingers': 'volume_down',
            'Four Fingers': 'play_pause',
            'Thumbs Up': 'mute',
        },
        'System Mode': {
            'Pinch': 'left_click',
        },
        'voice': {
            'App Mode': {
                'open_brave': 'open_brave',
                'open_apple_music': 'open_apple_music',
                'open_youtube': 'open_youtube',
                'close_window': 'close_window',
                'switch_tab': 'switch_tab',
                'scroll_down': 'scroll_down',
            },
            'Media Mode': {
                'play_song': 'play_pause',
                'pause': 'play_pause',
                'next_track': 'next_track',
                'previous_track': 'prev_track',
                'volume_up': 'volume_up',
                'volume_down': 'volume_down',
                'mute': 'mute',
            },
            'System Mode': {
                'open_brave': 'open_brave',
                'open_apple_music': 'open_apple_music',
                'open_youtube': 'open_youtube',
                'close_window': 'close_window',
                'switch_tab': 'switch_tab',
                'scroll_down': 'scroll_down',
                'play_song': 'play_pause',
                'pause': 'play_pause',
                'next_track': 'next_track',
                'previous_track': 'prev_track',
                'volume_up': 'volume_up',
                'volume_down': 'volume_down',
                'mute': 'mute',
            },
        },
        'action_whitelist': {
            'App Mode': [
                'open_brave',
                'open_apple_music',
                'open_browser',
                'open_music',
                'open_youtube',
                'close_window',
                'switch_tab',
                'scroll_down',
            ],
            'Media Mode': [
                'play_pause',
                'pause_media',
                'next_track',
                'prev_track',
                'previous_track',
                'volume_up',
                'volume_down',
                'mute',
            ],
            'System Mode': [
                'open_brave',
                'open_apple_music',
                'open_browser',
                'open_music',
                'open_youtube',
                'close_window',
                'switch_tab',
                'scroll_down',
                'play_pause',
                'pause_media',
                'next_track',
                'prev_track',
                'previous_track',
                'volume_up',
                'volume_down',
                'mute',
                'left_click',
                'right_click',
                'double_click',
            ],
        },
    }

    def __init__(
        self,
        config_path: str | Path | None = None,
        stability_frames: int = STABILITY_FRAMES,
        hold_seconds: float = HOLD_SECONDS,
        cooldown_seconds: float = COOLDOWN_SECONDS,
    ):
        self._mode_switch_map: dict[str, str] = {}
        self._voice_mode_switch_map: dict[str, str] = {}
        self._action_maps: dict[str, dict[str, str]] = {}
        self._voice_action_maps: dict[str, dict[str, str]] = {}
        self._action_whitelist: dict[str, set[str]] = {}

        self.current_mode: str = DEFAULT_MODE
        self._stability_frames = max(2, int(stability_frames))
        self._hold_seconds = max(0.1, float(hold_seconds))
        self._cooldown_seconds = max(0.1, float(cooldown_seconds))
        self._candidate_mode: str | None = None
        self._stable_count: int = 0
        self._hold_start: float = 0.0
        self._last_switch_time: float = 0.0

        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'gesture_map.json'
        self._config_path = Path(config_path)
        self._last_map_signature: tuple[int, int] | None = None
        self._last_reload_check: float = 0.0
        self._reload_check_interval_seconds: float = 0.2
        self._load_map(self._config_path)

    def set_runtime_timing(
        self,
        stability_frames: int | None = None,
        hold_seconds: float | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        """Update timing/stability knobs at runtime (used by calibration)."""
        if stability_frames is not None:
            self._stability_frames = max(2, int(stability_frames))
        if hold_seconds is not None:
            self._hold_seconds = max(0.1, float(hold_seconds))
        if cooldown_seconds is not None:
            self._cooldown_seconds = max(0.1, float(cooldown_seconds))

    def process(self, gesture: str | None) -> tuple[str | None, bool]:
        """Backward-compatible gesture path used by existing callers/tests."""
        self._maybe_reload_map()

        if gesture is None:
            self._reset_stability()
            return None, False

        if self.is_mode_switch(gesture):
            mode_changed = self._update_mode_stability(gesture)
            return None, mode_changed

        self._reset_stability()
        action = self.get_action(gesture, self.current_mode)
        return action, False

    def decide(self, event, mode: str | None = None) -> DecisionOutcome:
        """Resolve a normalized event containing type/command/confidence/timestamp."""
        self._maybe_reload_map()

        if event is None:
            self._reset_stability()
            return DecisionOutcome(reason='no_event')

        event_type = getattr(event, 'type', None)
        command = getattr(event, 'command', None)
        event_ts = float(getattr(event, 'timestamp', time.time()))
        target_mode = mode if mode is not None else self.current_mode

        if not event_type or not command:
            return DecisionOutcome(reason='invalid_event')

        if event_type == 'gesture' and command in self._mode_switch_map:
            mode_changed = self._update_mode_stability(command, now=event_ts)
            if mode_changed:
                return DecisionOutcome(target_mode=self.current_mode)
            return DecisionOutcome(reason='mode_switch_pending')

        if event_type == 'voice' and command in self._voice_mode_switch_map:
            mapped = self._voice_mode_switch_map.get(command)
            if mapped == _NEXT_MODE:
                idx = MODES.index(target_mode) if target_mode in MODES else 0
                return DecisionOutcome(target_mode=MODES[(idx + 1) % len(MODES)])
            if mapped in MODES:
                return DecisionOutcome(target_mode=mapped)

        self._reset_stability()
        action = self._lookup_action(event_type, command, target_mode)
        if not action:
            return DecisionOutcome(reason='unmapped_command')

        if action not in self._action_whitelist.get(target_mode, set()):
            return DecisionOutcome(reason='action_not_whitelisted')

        return DecisionOutcome(action=action)

    def get_action(self, gesture: str, mode: str | None = None) -> str | None:
        target_mode = mode if mode is not None else self.current_mode
        return self._action_maps.get(target_mode, {}).get(gesture)

    def get_voice_action(self, command: str, mode: str | None = None) -> str | None:
        target_mode = mode if mode is not None else self.current_mode
        action = self._voice_action_maps.get(target_mode, {}).get(command)
        if not action:
            return None
        if action not in self._action_whitelist.get(target_mode, set()):
            return None
        return action

    def is_mode_switch(self, gesture: str) -> bool:
        return gesture in self._mode_switch_map

    def resolve_mode_switch(self, gesture: str) -> str | None:
        return self._mode_switch_map.get(gesture)

    @property
    def mode_stability_progress(self) -> float:
        if self._candidate_mode is None:
            return 0.0
        frame_prog = min(self._stable_count / self._stability_frames, 1.0)
        if self._hold_start > 0:
            time_prog = min((time.time() - self._hold_start) / self._hold_seconds, 1.0)
        else:
            time_prog = 0.0
        return (frame_prog * 0.5 + time_prog * 0.5)

    def _update_mode_stability(self, gesture: str, now: float | None = None) -> bool:
        raw_target = self._mode_switch_map.get(gesture)
        tick = time.time() if now is None else float(now)

        if tick - self._last_switch_time < self._cooldown_seconds:
            return False

        if raw_target == _NEXT_MODE:
            idx = MODES.index(self.current_mode) if self.current_mode in MODES else 0
            target_mode = MODES[(idx + 1) % len(MODES)]
        else:
            target_mode = raw_target

        if target_mode != self._candidate_mode:
            self._candidate_mode = target_mode
            self._stable_count = 1
            self._hold_start = tick
            return False

        self._stable_count += 1
        if self._stable_count >= self._stability_frames and (tick - self._hold_start) >= self._hold_seconds:
            old_mode = self.current_mode
            self.current_mode = target_mode
            self._last_switch_time = tick
            ts = datetime.now().strftime('%H:%M:%S')
            print(f'[DecisionEngine] [{ts}] Mode Changed  {old_mode} -> {target_mode}')
            self._reset_stability()
            return True
        return False

    def _reset_stability(self) -> None:
        self._candidate_mode = None
        self._stable_count = 0
        self._hold_start = 0.0

    def _lookup_action(self, event_type: str, command: str, mode: str) -> str | None:
        if event_type == 'voice':
            return self._voice_action_maps.get(mode, {}).get(command)
        return self._action_maps.get(mode, {}).get(command)

    def _maybe_reload_map(self) -> None:
        now = time.time()
        if now - self._last_reload_check < self._reload_check_interval_seconds:
            return

        self._last_reload_check = now
        current_signature = self._read_map_signature(self._config_path)
        if self._last_map_signature != current_signature:
            self._load_map(self._config_path)

    @staticmethod
    def _read_map_signature(path: Path) -> tuple[int, int] | None:
        try:
            st = path.stat()
            return (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _load_map(self, path: Path) -> None:
        data: dict = {}
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            self._last_map_signature = self._read_map_signature(path)
            print(f'[DecisionEngine] Loaded gesture map from {path}')
        except FileNotFoundError:
            self._last_map_signature = None
            print('[DecisionEngine] gesture_map.json not found - using built-in defaults')
        except (json.JSONDecodeError, KeyError) as exc:
            self._last_map_signature = None
            print(f'[DecisionEngine] Warning: could not parse gesture map: {exc} - using defaults')
        except Exception as exc:
            self._last_map_signature = None
            print(f'[DecisionEngine] Warning: {exc} - using defaults')

        defaults = self._DEFAULT_MAPS

        raw_switch = data.get('mode_switch', {})
        validated_switch: dict[str, str] = {}
        for gesture, action in raw_switch.items():
            if action in ALLOWED_ACTIONS:
                validated_switch[gesture] = action
        self._mode_switch_map = {**defaults.get('mode_switch', {}), **validated_switch}

        raw_voice_switch = data.get('voice_mode_switch', {})
        validated_voice_switch: dict[str, str] = {}
        for command, target in raw_voice_switch.items():
            if target == _NEXT_MODE or target in MODES:
                validated_voice_switch[command] = target
        self._voice_mode_switch_map = {**defaults.get('voice_mode_switch', {}), **validated_voice_switch}

        for mode in MODES:
            raw_mode = data.get(mode, {})
            validated_mode: dict[str, str] = {}
            for gesture, action in raw_mode.items():
                if action in ALLOWED_ACTIONS:
                    validated_mode[gesture] = action
            self._action_maps[mode] = {**defaults.get(mode, {}), **validated_mode}

        raw_voice_maps = data.get('voice', {}) if isinstance(data.get('voice', {}), dict) else {}
        for mode in MODES:
            validated_voice_mode: dict[str, str] = {}
            raw_voice_mode = raw_voice_maps.get(mode, {}) if isinstance(raw_voice_maps, dict) else {}
            for command, action in raw_voice_mode.items():
                if action in ALLOWED_ACTIONS:
                    validated_voice_mode[command] = action
            self._voice_action_maps[mode] = {
                **defaults.get('voice', {}).get(mode, {}),
                **validated_voice_mode,
            }

        whitelist_defaults = defaults.get('action_whitelist', {})
        raw_whitelist = data.get('action_whitelist', {}) if isinstance(data.get('action_whitelist', {}), dict) else {}
        self._action_whitelist = {}
        for mode in MODES:
            if isinstance(raw_whitelist.get(mode), list):
                allowed = [action for action in raw_whitelist.get(mode, []) if action in ALLOWED_ACTIONS]
            else:
                allowed = list(whitelist_defaults.get(mode, []))
            self._action_whitelist[mode] = set(allowed)


_engine = DecisionEngine()


def get_action(mode: str, gesture: str) -> str | None:
    return _engine.get_action(gesture, mode)
