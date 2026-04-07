"""Compatibility facade for decision engine in core package."""

from engine.decision_engine import (
    ALLOWED_ACTIONS,
    COOLDOWN_SECONDS,
    DEFAULT_MODE,
    HOLD_SECONDS,
    MODES,
    STABILITY_FRAMES,
    DecisionEngine,
    DecisionOutcome,
    InputEvent,
    get_action,
)

__all__ = [
    'ALLOWED_ACTIONS',
    'COOLDOWN_SECONDS',
    'DEFAULT_MODE',
    'HOLD_SECONDS',
    'MODES',
    'STABILITY_FRAMES',
    'DecisionEngine',
    'DecisionOutcome',
    'InputEvent',
    'get_action',
]
