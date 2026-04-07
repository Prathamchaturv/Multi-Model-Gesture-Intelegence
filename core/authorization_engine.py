"""Compatibility facade for adaptive authorization engine in core package."""

from engine.adaptive_authorization import (
    AdaptiveAuthDecision,
    AdaptiveAuthorizationEngine,
    RiskLevel,
    UserState,
)

__all__ = [
    'AdaptiveAuthDecision',
    'AdaptiveAuthorizationEngine',
    'RiskLevel',
    'UserState',
]
