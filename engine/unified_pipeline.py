"""
Unified multimodal pipeline primitives and orchestration.

Pipeline
--------
Input (Gesture / Voice)
-> InputEventNormalizer
-> DecisionEngine
-> Security Layer (Face Authorization when enforcement is active)
-> ModeManager
-> ActionExecutor
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time

from core.face_security import FaceAuthResult, FaceSecurityManager
from core.authorization_engine import AdaptiveAuthorizationEngine
from execution.cursor_control import ActionExecutor
from core.decision_engine import DecisionEngine
from engine.runtime_controller import RuntimeController
from utils.logger import (
    log_action_executed,
    log_decision_made,
    log_input_received,
    log_pipeline_state,
    log_security_check,
)


class InputType(str, Enum):
    """Supported normalized input channels."""

    GESTURE = 'gesture'
    VOICE = 'voice'


@dataclass(frozen=True)
class InputEvent:
    """Canonical event format for all upstream modalities."""

    type: str
    command: str
    confidence: float
    timestamp: float


@dataclass(frozen=True)
class PipelineDecision:
    """Result payload from one pipeline tick."""

    action: str | None
    mode_changed: bool
    mode: str
    blocked_reason: str | None = None
    security_status: str | None = None
    auth_feedback: str | None = None
    user_state: str | None = None
    risk_level: str | None = None


@dataclass(frozen=True)
class ModeSwitchDecision:
    """Encapsulates mode transition details."""

    changed: bool
    mode: str


class InputEventNormalizer:
    """Converts raw gesture/voice payloads into normalized InputEvents."""

    @staticmethod
    def from_gesture(gesture: str, confidence: float, timestamp: float | None = None) -> InputEvent:
        return InputEvent(
            type=InputType.GESTURE.value,
            command=gesture,
            confidence=float(confidence),
            timestamp=time.time() if timestamp is None else float(timestamp),
        )

    @staticmethod
    def from_voice(command: str, confidence: float = 1.0, timestamp: float | None = None) -> InputEvent:
        return InputEvent(
            type=InputType.VOICE.value,
            command=command,
            confidence=float(confidence),
            timestamp=time.time() if timestamp is None else float(timestamp),
        )


class InputConflictResolver:
    """Deduplicates near-simultaneous gesture/voice events for the same action."""

    def __init__(self, duplicate_window_s: float = 0.25, prioritize_voice: bool = True) -> None:
        self._duplicate_window_s = float(duplicate_window_s)
        self._prioritize_voice = bool(prioritize_voice)
        self._last_event_by_action: dict[str, InputEvent] = {}

    def should_drop(self, action: str | None, event: InputEvent) -> bool:
        if not action:
            return False

        previous = self._last_event_by_action.get(action)
        if previous is None:
            self._last_event_by_action[action] = event
            return False

        if abs(event.timestamp - previous.timestamp) > self._duplicate_window_s:
            self._last_event_by_action[action] = event
            return False

        if self._prioritize_voice:
            if previous.type == InputType.VOICE.value and event.type != InputType.VOICE.value:
                return True
            if previous.type != InputType.VOICE.value and event.type == InputType.VOICE.value:
                self._last_event_by_action[action] = event
                return False

        return True


class ModeManager:
    """Owns active mode state and cooldown-protected switching."""

    DEFAULT_MODE = 'App Mode'

    def __init__(self, cooldown_s: float = 2.0, initial_mode: str = DEFAULT_MODE) -> None:
        self._cooldown_s = float(cooldown_s)
        self._current_mode = initial_mode
        self._last_switch_time = 0.0

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def set_mode(self, mode: str) -> None:
        self._current_mode = mode

    def configure(self, *, cooldown_s: float | None = None) -> None:
        """Adjust mode-switch policy at runtime via a stable public API."""
        if cooldown_s is not None:
            self._cooldown_s = max(0.0, float(cooldown_s))

    def apply_switch(self, target_mode: str, timestamp: float | None = None) -> ModeSwitchDecision:
        now = time.time() if timestamp is None else float(timestamp)
        if (now - self._last_switch_time) < self._cooldown_s:
            return ModeSwitchDecision(changed=False, mode=self._current_mode)

        if target_mode == self._current_mode:
            return ModeSwitchDecision(changed=False, mode=self._current_mode)

        self._current_mode = target_mode
        self._last_switch_time = now
        return ModeSwitchDecision(changed=True, mode=self._current_mode)


class UnifiedDecisionPipeline:
    """Executes the end-to-end multimodal action pipeline."""

    def __init__(
        self,
        decision_engine: DecisionEngine,
        action_executor: ActionExecutor,
        mode_manager: ModeManager,
        face_security: FaceSecurityManager | None = None,
        authorization_engine: AdaptiveAuthorizationEngine | None = None,
        conflict_resolver: InputConflictResolver | None = None,
        runtime_controller: RuntimeController | None = None,
    ) -> None:
        self._decision_engine = decision_engine
        self._action_executor = action_executor
        self._mode_manager = mode_manager
        self._face_security = face_security
        self._authorization_engine = authorization_engine
        self._conflict_resolver = conflict_resolver or InputConflictResolver()
        self._runtime_controller = runtime_controller

    def process_event(
        self,
        event: InputEvent,
        frame_bgr=None,
        enforce_face_security: bool = True,
        face_security_enabled: bool = False,
        face_verified: bool | None = None,
    ) -> PipelineDecision:
        """Resolve, authorize, and execute exactly one normalized input event."""
        log_input_received(event.type, event.command, event.confidence)

        decision = self._decision_engine.decide(event, self._mode_manager.current_mode)
        if self._runtime_controller is not None:
            self._runtime_controller.update_confidence(getattr(decision, 'confidence', event.confidence))
        log_decision_made(
            self._mode_manager.current_mode,
            event.command,
            decision.action,
            decision.reason,
        )
        target_mode = decision.target_mode
        mode_changed = False
        if target_mode:
            switch = self._mode_manager.apply_switch(target_mode, event.timestamp)
            self._decision_engine.current_mode = switch.mode
            mode_changed = switch.changed
            if switch.changed:
                log_pipeline_state(f'Mode changed to {switch.mode}')
            return PipelineDecision(
                action=None,
                mode_changed=mode_changed,
                mode=switch.mode,
            )

        action = decision.action
        if not action:
            return PipelineDecision(
                action=None,
                mode_changed=False,
                mode=self._mode_manager.current_mode,
            )

        if self._conflict_resolver.should_drop(action, event):
            return PipelineDecision(
                action=None,
                mode_changed=False,
                mode=self._mode_manager.current_mode,
                blocked_reason='conflict_duplicate_ignored',
            )

        auth_result: FaceAuthResult | None = None
        face_is_verified = bool(face_verified) if face_verified is not None else True
        if self._face_security is not None and face_verified is None:
            auth_result = self._face_security.evaluate(frame_bgr)
            face_is_verified = auth_result.is_authorized
            log_security_check(auth_result.is_authorized, auth_result.status_text)

        # Legacy compatibility path: preserve strict face blocking only when
        # adaptive authorization is not enabled.
        if self._authorization_engine is None and enforce_face_security and self._face_security is not None:
            if auth_result is None:
                auth_result = self._face_security.evaluate(frame_bgr)
                face_is_verified = auth_result.is_authorized
                log_security_check(auth_result.is_authorized, auth_result.status_text)
            if auth_result is not None and not auth_result.is_authorized:
                return PipelineDecision(
                    action=None,
                    mode_changed=False,
                    mode=self._mode_manager.current_mode,
                    blocked_reason='face_unauthorized',
                    security_status=auth_result.status_text,
                )

        if self._runtime_controller is not None:
            allowed, reason = self._runtime_controller.can_execute_action(
                action=action,
                face_authorized=True,
                activation_locked=False,
                confidence=getattr(decision, 'confidence', event.confidence),
            )
            if not allowed:
                return PipelineDecision(
                    action=None,
                    mode_changed=False,
                    mode=self._mode_manager.current_mode,
                    blocked_reason=reason,
                )

        auth_feedback = None
        user_state = None
        risk_level = None
        if self._authorization_engine is not None:
            authz = self._authorization_engine.authorize(
                action,
                face_security_enabled=bool(face_security_enabled),
                face_verified=face_is_verified,
                timestamp=event.timestamp,
            )
            auth_feedback = authz.feedback
            user_state = authz.user_state
            risk_level = authz.risk_level
            if not authz.execute:
                return PipelineDecision(
                    action=None,
                    mode_changed=False,
                    mode=self._mode_manager.current_mode,
                    blocked_reason=authz.reason or 'adaptive_authorization_pending',
                    security_status=auth_result.status_text if auth_result is not None else None,
                    auth_feedback=auth_feedback,
                    user_state=user_state,
                    risk_level=risk_level,
                )

        self._action_executor.execute(action)
        if self._runtime_controller is not None:
            self._runtime_controller.mark_action_executed()
        label = self._action_executor._LABELS.get(action, action)
        log_action_executed(label)

        return PipelineDecision(
            action=action,
            mode_changed=False,
            mode=self._mode_manager.current_mode,
            security_status=auth_result.status_text if auth_result is not None else None,
            auth_feedback=auth_feedback,
            user_state=user_state,
            risk_level=risk_level,
        )
