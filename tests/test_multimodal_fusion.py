"""
Unit tests for gesture + voice fusion in Media Mode.
"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.multimodal_fusion import MultiModalFusionEngine  # noqa: E402


def test_non_required_action_passes_without_voice() -> None:
    fusion = MultiModalFusionEngine(required_actions={'play_pause'})
    allow, matched = fusion.resolve(action='volume_up', mode='Media Mode', ts=100.0)
    assert allow is True
    assert matched is None


def test_required_action_blocked_without_voice() -> None:
    fusion = MultiModalFusionEngine(required_actions={'play_pause'})
    allow, matched = fusion.resolve(action='play_pause', mode='Media Mode', ts=100.0)
    assert allow is False
    assert matched is None


def test_required_action_passes_with_matching_voice() -> None:
    fusion = MultiModalFusionEngine(required_actions={'play_pause'}, command_ttl_s=2.0)
    fusion.update_voice('play_song', ts=100.0)
    allow, matched = fusion.resolve(action='play_pause', mode='Media Mode', ts=101.0)
    assert allow is True
    assert matched == 'play_song'


def test_required_action_rejects_mismatched_voice() -> None:
    fusion = MultiModalFusionEngine(required_actions={'mute'}, command_ttl_s=2.0)
    fusion.update_voice('play_song', ts=100.0)
    allow, matched = fusion.resolve(action='mute', mode='Media Mode', ts=101.0)
    assert allow is False
    assert matched is None


def test_voice_command_expires() -> None:
    fusion = MultiModalFusionEngine(required_actions={'play_pause'}, command_ttl_s=1.0)
    fusion.update_voice('play_song', ts=100.0)
    allow, matched = fusion.resolve(action='play_pause', mode='Media Mode', ts=101.5)
    assert allow is False
    assert matched is None


def test_fusion_only_applies_in_media_mode() -> None:
    fusion = MultiModalFusionEngine(required_actions={'play_pause'})
    allow, matched = fusion.resolve(action='play_pause', mode='App Mode', ts=100.0)
    assert allow is True
    assert matched is None
