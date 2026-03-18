"""
Module: auth_state.py
Description: Lightweight in-memory authentication session state for MMGI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class AuthSession:
    """Tracks authentication state for the current app runtime session."""

    is_authenticated: bool = False
    username: str = ''
    login_time: float = 0.0

    def set_authenticated(self, username: str) -> None:
        self.is_authenticated = True
        self.username = username
        self.login_time = time.time()

    def reset(self) -> None:
        self.is_authenticated = False
        self.username = ''
        self.login_time = 0.0


auth_state = AuthSession()
