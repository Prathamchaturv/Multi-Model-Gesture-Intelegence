"""Adaptive authorization for multimodal action execution.

This module applies risk-aware execution confirmation without turning gesture
control into a hard-deny security gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time


class RiskLevel(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class UserState(str, Enum):
    OPEN = 'open'
    RESTRICTED = 'restricted'
    TRUSTED = 'trusted'


@dataclass(frozen=True)
class AdaptiveAuthDecision:
    execute: bool
    feedback: str
    user_state: str
    risk_level: str
    reason: str | None = None


@dataclass
class _ActionTrack:
    count: int = 0
    first_ts: float = 0.0
    last_ts: float = 0.0


class AdaptiveAuthorizationEngine:
    """Risk-based action confirmer with role-adaptive thresholds."""

    DEFAULT_ACTION_RISK_MAP: dict[str, RiskLevel] = {
        # Low risk
        'open_brave': RiskLevel.LOW,
        'open_apple_music': RiskLevel.LOW,
        'open_youtube': RiskLevel.LOW,
        'scroll_down': RiskLevel.LOW,
        'scroll_up': RiskLevel.LOW,
        # Medium risk
        'switch_tab': RiskLevel.MEDIUM,
        'volume_up': RiskLevel.MEDIUM,
        'volume_down': RiskLevel.MEDIUM,
        'next_track': RiskLevel.MEDIUM,
        'prev_track': RiskLevel.MEDIUM,
        'play_pause': RiskLevel.MEDIUM,
        'mute': RiskLevel.MEDIUM,
        'left_click': RiskLevel.MEDIUM,
        'right_click': RiskLevel.MEDIUM,
        # High risk
        'double_click': RiskLevel.HIGH,
        'close_window': RiskLevel.HIGH,
    }

    _MEDIUM_CONFIRM_FRAMES: dict[UserState, int] = {
        UserState.OPEN: 2,
        UserState.RESTRICTED: 4,
        UserState.TRUSTED: 2,
    }

    _HIGH_CONFIRM_FRAMES: dict[UserState, int] = {
        UserState.OPEN: 3,
        UserState.RESTRICTED: 5,
        UserState.TRUSTED: 2,
    }

    _HIGH_HOLD_SECONDS: dict[UserState, float] = {
        UserState.OPEN: 0.75,
        UserState.RESTRICTED: 1.10,
        UserState.TRUSTED: 0.45,
    }

    def __init__(
        self,
        action_risk_map: dict[str, str | RiskLevel] | None = None,
        restricted_high_risk_actions: set[str] | None = None,
        max_inter_event_gap_s: float = 0.35,
        tracker_ttl_s: float = 3.0,
    ) -> None:
        self._risk_map: dict[str, RiskLevel] = dict(self.DEFAULT_ACTION_RISK_MAP)
        if action_risk_map:
            for action, raw_level in action_risk_map.items():
                self._risk_map[action] = self._coerce_risk_level(raw_level)

        self._restricted_high_risk_actions = set(restricted_high_risk_actions or {'close_window'})
        self._max_inter_event_gap_s = max(0.05, float(max_inter_event_gap_s))
        self._tracker_ttl_s = max(1.0, float(tracker_ttl_s))

        self._track_by_action: dict[str, _ActionTrack] = {}

    @staticmethod
    def resolve_user_state(face_security_enabled: bool, face_verified: bool) -> UserState:
        if not face_security_enabled:
            return UserState.OPEN
        if face_verified:
            return UserState.TRUSTED
        return UserState.RESTRICTED

    def authorize(
        self,
        action: str,
        *,
        face_security_enabled: bool,
        face_verified: bool,
        timestamp: float | None = None,
    ) -> AdaptiveAuthDecision:
        now = time.time() if timestamp is None else float(timestamp)
        self._gc_trackers(now)

        risk = self._risk_map.get(action, RiskLevel.MEDIUM)
        user_state = self.resolve_user_state(face_security_enabled, face_verified)

        if risk == RiskLevel.LOW:
            self._track_by_action.pop(action, None)
            return AdaptiveAuthDecision(
                execute=True,
                feedback='Executed',
                user_state=user_state.value,
                risk_level=risk.value,
            )

        track = self._next_track(action, now)

        if risk == RiskLevel.MEDIUM:
            needed_frames = self._MEDIUM_CONFIRM_FRAMES[user_state]
            if track.count < needed_frames:
                return AdaptiveAuthDecision(
                    execute=False,
                    feedback='Stabilizing...',
                    user_state=user_state.value,
                    risk_level=risk.value,
                    reason='medium_risk_stability_pending',
                )
            self._track_by_action.pop(action, None)
            return AdaptiveAuthDecision(
                execute=True,
                feedback='Executed',
                user_state=user_state.value,
                risk_level=risk.value,
            )

        # High risk path
        if user_state == UserState.RESTRICTED and action in self._restricted_high_risk_actions:
            return AdaptiveAuthDecision(
                execute=False,
                feedback='Access Controlled',
                user_state=user_state.value,
                risk_level=risk.value,
                reason='high_risk_restricted_partial_block',
            )

        needed_frames = self._HIGH_CONFIRM_FRAMES[user_state]
        if track.count < needed_frames:
            return AdaptiveAuthDecision(
                execute=False,
                feedback='Stabilizing...',
                user_state=user_state.value,
                risk_level=risk.value,
                reason='high_risk_stability_pending',
            )

        held_for = now - track.first_ts
        needed_hold = self._HIGH_HOLD_SECONDS[user_state]
        if held_for < needed_hold:
            return AdaptiveAuthDecision(
                execute=False,
                feedback='Hold to Confirm',
                user_state=user_state.value,
                risk_level=risk.value,
                reason='high_risk_hold_pending',
            )

        self._track_by_action.pop(action, None)
        return AdaptiveAuthDecision(
            execute=True,
            feedback='Executed',
            user_state=user_state.value,
            risk_level=risk.value,
        )

    def _next_track(self, action: str, now: float) -> _ActionTrack:
        track = self._track_by_action.get(action)
        if track is None or (now - track.last_ts) > self._max_inter_event_gap_s:
            track = _ActionTrack(count=1, first_ts=now, last_ts=now)
            self._track_by_action[action] = track
            return track

        track.count += 1
        track.last_ts = now
        return track

    def _gc_trackers(self, now: float) -> None:
        stale = [
            action for action, track in self._track_by_action.items()
            if (now - track.last_ts) > self._tracker_ttl_s
        ]
        for action in stale:
            self._track_by_action.pop(action, None)

    @staticmethod
    def _coerce_risk_level(raw_level: str | RiskLevel) -> RiskLevel:
        if isinstance(raw_level, RiskLevel):
            return raw_level
        normalized = str(raw_level).strip().lower()
        if normalized == RiskLevel.LOW.value:
            return RiskLevel.LOW
        if normalized == RiskLevel.HIGH.value:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
