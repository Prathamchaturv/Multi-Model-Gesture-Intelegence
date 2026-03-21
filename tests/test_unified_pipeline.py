"""Unit tests for the unified multimodal decision pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.face_security import FaceAuthResult  # noqa: E402
from engine.action_executor import ActionExecutor  # noqa: E402
from engine.decision_engine import DecisionEngine  # noqa: E402
from engine.unified_pipeline import (  # noqa: E402
    InputConflictResolver,
    InputEventNormalizer,
    ModeManager,
    UnifiedDecisionPipeline,
)


class _AllowAllFaceSecurity:
    def evaluate(self, frame_bgr):
        return FaceAuthResult(
            is_authorized=True,
            status_text='authorized',
            face_detected=True,
            user_present=True,
            system_paused=False,
            similarity=0.99,
        )


class _DenyAllFaceSecurity:
    def evaluate(self, frame_bgr):
        return FaceAuthResult(
            is_authorized=False,
            status_text='Unknown User X',
            face_detected=True,
            user_present=True,
            system_paused=False,
            similarity=0.25,
        )


class _SpyExecutor(ActionExecutor):
    def __init__(self):
        super().__init__()
        self.executed: list[str] = []

    def execute(self, action: str) -> None:
        self.executed.append(action)


def test_input_event_normalizer_fields() -> None:
    event = InputEventNormalizer.from_gesture('Two Fingers', confidence=0.82, timestamp=100.0)
    assert event.type == 'gesture'
    assert event.command == 'Two Fingers'
    assert event.confidence == 0.82
    assert event.timestamp == 100.0


def test_decision_engine_voice_mapping_for_media_mode() -> None:
    engine = DecisionEngine()
    event = InputEventNormalizer.from_voice('play_song', timestamp=101.0)
    outcome = engine.decide(event, mode='Media Mode')
    assert outcome.action == 'play_pause'
    assert outcome.reason is None


def test_mode_manager_applies_cooldown() -> None:
    manager = ModeManager(cooldown_s=2.0, initial_mode='App Mode')
    first = manager.apply_switch('Media Mode', timestamp=100.0)
    second = manager.apply_switch('System Mode', timestamp=100.5)
    assert first.changed is True
    assert second.changed is False
    assert manager.current_mode == 'Media Mode'


def test_pipeline_blocks_unauthorized_system_action() -> None:
    engine = DecisionEngine()
    executor = _SpyExecutor()
    manager = ModeManager(initial_mode='System Mode')
    pipeline = UnifiedDecisionPipeline(
        decision_engine=engine,
        action_executor=executor,
        mode_manager=manager,
        face_security=_DenyAllFaceSecurity(),
    )

    voice_event = InputEventNormalizer.from_voice('open_brave', timestamp=110.0)
    result = pipeline.process_event(voice_event, frame_bgr=None)

    assert result.action is None
    assert result.blocked_reason == 'face_unauthorized'
    assert executor.executed == []


def test_conflict_resolver_prioritizes_voice() -> None:
    resolver = InputConflictResolver(duplicate_window_s=0.4, prioritize_voice=True)

    gesture_event = InputEventNormalizer.from_gesture('Two Fingers', 0.9, timestamp=200.0)
    voice_event = InputEventNormalizer.from_voice('volume_down', timestamp=200.1)
    extra_gesture = InputEventNormalizer.from_gesture('Two Fingers', 0.9, timestamp=200.2)

    assert resolver.should_drop('volume_down', gesture_event) is False
    assert resolver.should_drop('volume_down', voice_event) is False
    assert resolver.should_drop('volume_down', extra_gesture) is True


def test_decision_engine_respects_action_whitelist() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / 'gesture_map.json'
        data = {
            'mode_switch': {'Three Fingers': 'next_mode'},
            'App Mode': {'One Finger': 'open_brave'},
            'Media Mode': {},
            'System Mode': {},
            'voice': {
                'App Mode': {'open_brave': 'open_brave'},
                'Media Mode': {},
                'System Mode': {},
            },
            'action_whitelist': {
                'App Mode': ['open_apple_music'],
                'Media Mode': [],
                'System Mode': [],
            },
        }
        with open(cfg_path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)

        engine = DecisionEngine(config_path=cfg_path)
        event = InputEventNormalizer.from_voice('open_brave', timestamp=300.0)
        outcome = engine.decide(event, mode='App Mode')
        assert outcome.action is None
        assert outcome.reason == 'action_not_whitelisted'
