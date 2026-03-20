"""
Module: activation_manager.py
Description: Safety gate for gesture execution — requires Open Palm held for
             2 seconds to activate and Fist to deactivate instantly, preventing
             accidental command firing.
Author: Pratham Chaturvedi

engine/activation_manager.py - The Safety Gatekeeper

Manages the system's active/inactive state with multiple safety layers:

    • Activation   : hold "Open Palm" for 2 seconds (no accidental triggers)
    • Deactivation : show "Fist" for instant off
    • Stability    : gesture must be consistent for ≥ 10 frames
    • Cooldown     : 1-second wait between actions (prevents rapid repeats)
    • Visual panel : always shows INACTIVE / ACTIVATING / ACTIVE with a
                     progress bar during the activation countdown
"""

import time
import cv2


class ActivationManager:
    """State machine that gates gesture execution behind a safety protocol."""

    STATE_INACTIVE   = 'INACTIVE'
    STATE_ACTIVATING = 'ACTIVATING'
    STATE_ACTIVE     = 'ACTIVE'

    # Gestures that should never trigger an action (system-only)
    _SYSTEM_GESTURES = frozenset({'Open Palm', 'Fist', 'Unknown', 'Thumbs Up'})

    def __init__(
        self,
        open_palm_duration: float = 2.0,
        cooldown_duration:  float = 1.0,
        stability_threshold: int  = 10,
    ):
        self._open_palm_duration  = open_palm_duration
        self._cooldown_duration   = cooldown_duration
        self._stability_threshold = stability_threshold

        # State tracking
        self._state: str            = self.STATE_INACTIVE
        self._activation_start: float | None = None
        self._last_action_time: float        = 0.0

        # Stability tracking
        self._last_gesture: str | None = None
        self._stable_count: int        = 0
        self._last_triggered: str | None = None  # last gesture that fired

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._state == self.STATE_ACTIVE

    @property
    def is_in_cooldown(self) -> bool:
        return (time.time() - self._last_action_time) < self._cooldown_duration

    @property
    def state(self) -> str:
        return self._state

    def force_inactive(self, reason: str | None = None) -> None:
        """Force the gate into INACTIVE state immediately."""
        if self._state != self.STATE_INACTIVE:
            self._state = self.STATE_INACTIVE
            self._activation_start = None
            self._last_triggered = None
            if reason:
                print(f'! System locked: {reason}')

    # ------------------------------------------------------------------
    # Main update — called once per frame
    # ------------------------------------------------------------------

    def update(self, gesture: str | None) -> bool:
        """
        Process the current gesture and update internal state.

        Returns True **only** when a non-system gesture has been held
        steadily and the system is active + not in cooldown.
        The caller should execute the corresponding action on True.
        """
        now = time.time()

        # ---- Stability counter ----------------------------------------
        if gesture == self._last_gesture:
            self._stable_count += 1
        else:
            self._stable_count = 0
            self._last_gesture = gesture

        stable = self._stable_count >= self._stability_threshold

        # ---- Handle None / no hand -------------------------------------
        if gesture is None:
            if self._state == self.STATE_ACTIVATING:
                self._state = self.STATE_INACTIVE
                self._activation_start = None
            return False

        # ---- Activation flow ------------------------------------------
        if gesture == 'Open Palm':
            if self._state == self.STATE_INACTIVE:
                self._state = self.STATE_ACTIVATING
                self._activation_start = now

            if self._state == self.STATE_ACTIVATING:
                elapsed = now - self._activation_start
                if elapsed >= self._open_palm_duration:
                    self._state = self.STATE_ACTIVE
                    self._last_action_time = now  # brief cooldown grace
                    print('✓ System ACTIVATED')
            return False

        # Open Palm gesture released — cancel activation countdown
        if self._state == self.STATE_ACTIVATING:
            self._state = self.STATE_INACTIVE
            self._activation_start = None

        # ---- Deactivation flow ----------------------------------------
        if gesture == 'Fist' and self._state == self.STATE_ACTIVE:
            self._state = self.STATE_INACTIVE
            self._last_triggered = None
            print('✕ System DEACTIVATED')
            return False

        # ---- Action trigger -------------------------------------------
        if (
            self._state == self.STATE_ACTIVE
            and stable
            and gesture not in self._SYSTEM_GESTURES
            and not self.is_in_cooldown
        ):
            # Fire only when gesture changes OR cooldown fully elapsed
            if gesture != self._last_triggered or (now - self._last_action_time) >= self._cooldown_duration:
                self._last_triggered  = gesture
                self._last_action_time = now
                print(f'→ Stable gesture triggered: {gesture}')
                return True

        return False

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def display_status(self, frame):
        """Draw a translucent status panel in the bottom-left corner."""
        h, w = frame.shape[:2]

        px, py = 10, h - 105
        pw, ph = 260, 90

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (px, py), (px + pw, py + ph), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        cv2.rectangle(frame, (px, py), (px + pw, py + ph), (80, 80, 80), 1)

        # State colour and label
        if self._state == self.STATE_INACTIVE:
            colour = (60,  60, 220)
            label  = 'INACTIVE'
        elif self._state == self.STATE_ACTIVATING:
            colour = (20, 200, 255)
            label  = 'ACTIVATING'
        else:
            colour = (30, 210,  40)
            label  = 'ACTIVE'

        cv2.putText(
            frame, f'Status: {label}',
            (px + 8, py + 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.62, colour, 2, cv2.LINE_AA,
        )

        # Progress bar (shown only while activating)
        if self._state == self.STATE_ACTIVATING and self._activation_start:
            elapsed  = time.time() - self._activation_start
            progress = min(elapsed / self._open_palm_duration, 1.0)

            bx, by = px + 8, py + 45
            bw, bh = pw - 16, 14

            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (60, 60, 60), -1)
            fill = int(bw * progress)
            cv2.rectangle(frame, (bx, by), (bx + fill, by + bh), (20, 200, 255), -1)
            cv2.putText(
                frame, f'{progress * 100:.0f}%',
                (bx + bw // 2 - 14, by + bh - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA,
            )

        # Cooldown indicator
        if self._state == self.STATE_ACTIVE and self.is_in_cooldown:
            remaining = self._cooldown_duration - (time.time() - self._last_action_time)
            cv2.putText(
                frame, f'Cooldown: {remaining:.1f}s',
                (px + 8, py + 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 165, 0), 1, cv2.LINE_AA,
            )

        return frame
