"""Compatibility facade for voice processing engine."""

from core.voice_control import (
    VoiceCommandEvent,
    VoiceCommandListener,
    normalize_voice_command,
)

__all__ = [
    'VoiceCommandEvent',
    'VoiceCommandListener',
    'normalize_voice_command',
]
