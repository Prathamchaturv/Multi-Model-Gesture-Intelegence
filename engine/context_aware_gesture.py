"""Context-aware gesture routing for Windows desktop applications.

This module exposes three primary functions:
1) detect_active_window() -> ActiveWindowInfo
2) get_context() -> str (browser | media | system)
3) handle_gesture(gesture, context) -> str | None

The router is intentionally small and production-focused so it can be
reused from the UI worker, headless loop, or tests.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform
from pathlib import Path
import time
from typing import Literal
import json

try:
    import psutil
    import win32gui
    import win32process

    _WINDOW_LIBS_AVAILABLE = True
except Exception:
    _WINDOW_LIBS_AVAILABLE = False


ContextType = Literal['browser', 'media', 'system']


@dataclass(frozen=True)
class ActiveWindowInfo:
    """Metadata for the current foreground window."""

    title: str
    process_name: str
    executable: str


_BROWSER_KEYWORDS = {
    'chrome',
    'msedge',
    'firefox',
    'brave',
    'opera',
    'vivaldi',
    'arc',
    'browser',
}

_MEDIA_KEYWORDS = {
    'vlc',
    'spotify',
    'music',
    'itunes',
    'potplayer',
    'wmplayer',
    'youtube',
    'netflix',
    'prime video',
    'disney',
}

_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'context_routing.json'
_CACHE_REFRESH_S = 1.0
_last_keyword_refresh_ts = 0.0
_cached_browser_keywords = set(_BROWSER_KEYWORDS)
_cached_media_keywords = set(_MEDIA_KEYWORDS)


def _normalize_keyword_items(items) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {_normalize(item) for item in items if isinstance(item, str) and _normalize(item)}


def _load_keywords_from_config() -> tuple[set[str], set[str]]:
    if not _CONFIG_PATH.exists():
        return set(_BROWSER_KEYWORDS), set(_MEDIA_KEYWORDS)

    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as fh:
            payload = json.load(fh)
    except Exception:
        return set(_BROWSER_KEYWORDS), set(_MEDIA_KEYWORDS)

    if not isinstance(payload, dict):
        return set(_BROWSER_KEYWORDS), set(_MEDIA_KEYWORDS)

    browser = _normalize_keyword_items(payload.get('browser_keywords'))
    media = _normalize_keyword_items(payload.get('media_keywords'))
    return (
        browser or set(_BROWSER_KEYWORDS),
        media or set(_MEDIA_KEYWORDS),
    )


def _get_keyword_sets() -> tuple[set[str], set[str]]:
    global _last_keyword_refresh_ts, _cached_browser_keywords, _cached_media_keywords

    now = time.time()
    if (now - _last_keyword_refresh_ts) >= _CACHE_REFRESH_S:
        _cached_browser_keywords, _cached_media_keywords = _load_keywords_from_config()
        _last_keyword_refresh_ts = now
    return _cached_browser_keywords, _cached_media_keywords


_CONTEXT_GESTURE_MAP: dict[ContextType, dict[str, str]] = {
    'browser': {
        'swipe_up': 'scroll_up',
        'swipe_down': 'scroll_down',
        'swipe_left': 'scroll_up',
        'swipe_right': 'scroll_down',
    },
    'media': {
        'swipe_left': 'seek_backward',
        'swipe_right': 'seek_forward',
        'swipe_up': 'volume_up',
        'swipe_down': 'volume_down',
    },
    'system': {
        'swipe_left': 'switch_apps',
        'swipe_right': 'switch_apps',
        'swipe_up': 'switch_apps',
        'swipe_down': 'switch_apps',
    },
}


def _normalize(value: str | None) -> str:
    return (value or '').strip().lower()


def _normalize_gesture(gesture: str) -> str:
    return _normalize(gesture).replace(' ', '_')


def detect_active_window() -> ActiveWindowInfo:
    """Return active foreground window details on Windows.

    Returns empty values if the platform or required libraries are unavailable.
    """
    if platform.system() != 'Windows' or not _WINDOW_LIBS_AVAILABLE:
        return ActiveWindowInfo(title='', process_name='', executable='')

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return ActiveWindowInfo(title='', process_name='', executable='')

    title = win32gui.GetWindowText(hwnd) or ''
    _, pid = win32process.GetWindowThreadProcessId(hwnd)

    try:
        proc = psutil.Process(pid)
        process_name = proc.name() or ''
        executable = proc.exe() or ''
    except (psutil.Error, OSError):
        process_name = ''
        executable = ''

    return ActiveWindowInfo(
        title=title,
        process_name=process_name,
        executable=executable,
    )


def get_context(window: ActiveWindowInfo | None = None) -> ContextType:
    """Classify the active context as browser, media, or system."""
    info = window or detect_active_window()
    browser_keywords, media_keywords = _get_keyword_sets()
    blob = ' '.join([
        _normalize(info.title),
        _normalize(info.process_name),
        _normalize(info.executable),
    ])

    # Prioritize media when a browser tab is actively playing content.
    if any(token in blob for token in media_keywords):
        return 'media'
    if any(token in blob for token in browser_keywords):
        return 'browser'
    return 'system'


def handle_gesture(gesture: str, context: ContextType) -> str | None:
    """Resolve a gesture to an action for the specified context.

    Example mappings:
    - browser + swipe -> scroll actions
    - media + swipe -> seek actions
    - system + swipe -> app switch action
    """
    gesture_key = _normalize_gesture(gesture)
    context_map = _CONTEXT_GESTURE_MAP.get(context, {})
    return context_map.get(gesture_key)


__all__ = [
    'ActiveWindowInfo',
    'ContextType',
    'detect_active_window',
    'get_context',
    'handle_gesture',
]
