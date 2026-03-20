"""Unit tests for voice command normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.voice_control import normalize_voice_command  # noqa: E402


def test_normalize_open_brave_command() -> None:
    assert normalize_voice_command('Open Brave') == 'open_brave'
    assert normalize_voice_command('launch brave browser') == 'open_brave'


def test_normalize_open_music_command() -> None:
    assert normalize_voice_command('open apple music') == 'open_apple_music'


def test_normalize_media_commands() -> None:
    assert normalize_voice_command('volume up') == 'volume_up'
    assert normalize_voice_command('next track') == 'next_track'
    assert normalize_voice_command('mute') == 'mute'


def test_normalize_system_navigation_commands() -> None:
    assert normalize_voice_command('open youtube') == 'open_youtube'
    assert normalize_voice_command('close window') == 'close_window'
    assert normalize_voice_command('switch tab') == 'switch_tab'
    assert normalize_voice_command('scroll down') == 'scroll_down'


def test_normalize_unknown_command_returns_none() -> None:
    assert normalize_voice_command('what is the weather today') is None
