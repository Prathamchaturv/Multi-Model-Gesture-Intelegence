"""Integration tests for MMGI gesture/voice control flow.

Covers end-to-end pipeline behavior with mocked external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.face_security import FaceAuthResult
from core.decision_engine import DecisionEngine
from engine.unified_pipeline import InputEventNormalizer, ModeManager, UnifiedDecisionPipeline
from execution.cursor_control import ActionExecutor


@dataclass
class _SpyExecutor:
    """Minimal executor spy so tests never trigger real OS automation."""

    executed: list[str]

    def execute(self, action: str) -> None:
        self.executed.append(action)

    _LABELS = {
        'open_brave': 'Open Brave',
        'open_apple_music': 'Open Apple Music',
        'play_pause': 'Play/Pause',
        'volume_down': 'Volume Down',
    }


class _AllowFaceSecurity:
    def evaluate(self, frame_bgr):
        return FaceAuthResult(
            is_authorized=True,
            status_text='authorized',
            face_detected=True,
            user_present=True,
            system_paused=False,
            similarity=0.99,
        )


class _DenyFaceSecurity:
    def evaluate(self, frame_bgr):
        return FaceAuthResult(
            is_authorized=False,
            status_text='unauthorized',
            face_detected=True,
            user_present=True,
            system_paused=False,
            similarity=0.20,
        )


@pytest.fixture
def integration_pipeline_allow() -> tuple[UnifiedDecisionPipeline, ModeManager, _SpyExecutor]:
    """Pipeline fixture with authorized face results and mocked executor."""
    decision_engine = DecisionEngine()
    mode_manager = ModeManager(initial_mode='App Mode')
    executor = _SpyExecutor(executed=[])
    pipeline = UnifiedDecisionPipeline(
        decision_engine=decision_engine,
        action_executor=executor,  # type: ignore[arg-type]
        mode_manager=mode_manager,
        face_security=_AllowFaceSecurity(),
    )
    return pipeline, mode_manager, executor


@pytest.fixture
def integration_pipeline_deny() -> tuple[UnifiedDecisionPipeline, ModeManager, _SpyExecutor]:
    """Pipeline fixture with unauthorized face results and mocked executor."""
    decision_engine = DecisionEngine()
    mode_manager = ModeManager(initial_mode='System Mode')
    executor = _SpyExecutor(executed=[])
    pipeline = UnifiedDecisionPipeline(
        decision_engine=decision_engine,
        action_executor=executor,  # type: ignore[arg-type]
        mode_manager=mode_manager,
        face_security=_DenyFaceSecurity(),
    )
    return pipeline, mode_manager, executor


@pytest.mark.integration
def test_gesture_to_action_execution(integration_pipeline_allow) -> None:
    """Gesture input should resolve and execute the expected action."""
    pipeline, mode_manager, executor = integration_pipeline_allow

    mode_manager.set_mode('App Mode')
    event = InputEventNormalizer.from_gesture('Two Fingers', confidence=0.95, timestamp=100.0)
    result = pipeline.process_event(event, frame_bgr=Mock())

    assert result.action == 'open_apple_music'
    assert executor.executed == ['open_apple_music']


@pytest.mark.integration
def test_voice_to_command_mapping_execution(integration_pipeline_allow) -> None:
    """Voice command should map correctly and execute through the pipeline."""
    pipeline, mode_manager, executor = integration_pipeline_allow

    mode_manager.set_mode('Media Mode')
    event = InputEventNormalizer.from_voice('play_song', confidence=0.97, timestamp=110.0)
    result = pipeline.process_event(event, frame_bgr=Mock())

    assert result.action == 'play_pause'
    assert executor.executed[-1] == 'play_pause'


@pytest.mark.integration
def test_mode_switching_app_media_system_cycle(integration_pipeline_allow) -> None:
    """Voice-driven mode switching should cycle App -> Media -> System -> App."""
    pipeline, mode_manager, _ = integration_pipeline_allow

    mode_manager.set_mode('App Mode')

    e1 = InputEventNormalizer.from_voice('next_mode', confidence=1.0, timestamp=200.0)
    r1 = pipeline.process_event(e1, frame_bgr=Mock())
    assert r1.mode_changed is True
    assert mode_manager.current_mode == 'Media Mode'

    e2 = InputEventNormalizer.from_voice('next_mode', confidence=1.0, timestamp=203.0)
    r2 = pipeline.process_event(e2, frame_bgr=Mock())
    assert r2.mode_changed is True
    assert mode_manager.current_mode == 'System Mode'

    e3 = InputEventNormalizer.from_voice('next_mode', confidence=1.0, timestamp=206.0)
    r3 = pipeline.process_event(e3, frame_bgr=Mock())
    assert r3.mode_changed is True
    assert mode_manager.current_mode == 'App Mode'


@pytest.mark.integration
@pytest.mark.security
def test_face_authorization_gating_blocks_action(integration_pipeline_deny) -> None:
    """Unauthorized face result should block action execution in secured flow."""
    pipeline, mode_manager, executor = integration_pipeline_deny

    mode_manager.set_mode('System Mode')
    event = InputEventNormalizer.from_voice('open_brave', confidence=0.95, timestamp=300.0)
    result = pipeline.process_event(event, frame_bgr=Mock(), enforce_face_security=True)

    assert result.action is None
    assert result.blocked_reason == 'face_unauthorized'
    assert executor.executed == []


@pytest.mark.integration
def test_mock_camera_example(mock_camera) -> None:
    """Mock example: camera source is replaced with a synthetic frame provider."""
    ok, frame = mock_camera.read()

    assert ok is True
    assert frame.shape == (480, 640, 3)


@pytest.mark.integration
def test_mock_os_action_example_prevents_real_side_effects() -> None:
    """Mock example: patch browser launch so no real OS action is performed."""
    with patch('engine.action_executor.webbrowser.open') as open_mock:
        executor = ActionExecutor(config={})
        executor.execute('open_youtube')

    open_mock.assert_called_once_with('https://www.youtube.com', new=2)
