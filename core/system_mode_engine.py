"""
Module: system_mode_engine.py
Description: System Mode air-mouse engine — translates hand landmarks into
             Win32 mouse events with index-tip cursor movement and pinch click,
             using EMA smoothing and rising-edge detection.
Author: Pratham Chaturvedi

core/system_mode_engine.py - System Mode Air Mouse Engine

Provides full air-mouse control when 'System Mode' is active:

    Gesture / pose      →  Mouse action
    ─────────────────────────────────────────────────────────
    Index fingertip     →  Move cursor  (continuous)
    Thumb+index pinch   →  Left click   (rising edge)
    Two Fingers         →  Scroll       (optional, backward compatible)
    Thumb, Index, Middle and Ring →  Right click  (optional, backward compatible)
    Thumbs Up           →  Double-click (optional, backward compatible)
    Three Fingers       →  Mode switch  (handled by DecisionEngine upstream)
    Open Palm / Fist    →  Activate / Deactivate  (ActivationManager upstream)

Uses ctypes.windll.user32 for all Win32 input — no extra dependencies.
Applies Exponential Moving Average (EMA) smoothing to eliminate hand jitter.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import time
from dataclasses import dataclass
from datetime    import datetime


# ---------------------------------------------------------------------------
# Win32 mouse-event flags
# ---------------------------------------------------------------------------

_MOUSEEVENTF_LEFTDOWN  = 0x0002
_MOUSEEVENTF_LEFTUP    = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP   = 0x0010
_MOUSEEVENTF_WHEEL     = 0x0800

_DOUBLE_CLICK_PAUSE_S  = 0.05   # seconds between the two clicks of a double-click


# ---------------------------------------------------------------------------
# AirMouseController
# ---------------------------------------------------------------------------

class AirMouseController:
    """
    Translates hand-landmark positions and gestures into Win32 mouse events.

    Parameters
    ----------
    smoothing : float
        EMA alpha for cursor smoothing (0–1).  Lower = smoother but laggier.
        Recommended range: 0.15–0.35.  Default 0.25.
    dead_zone : int
        Pixel radius below which cursor moves are suppressed (reduces micro-jitter).
        Default 4.
    input_margin : float
        Fraction of the normalised camera frame to crop from each edge as the
        control zone (e.g. 0.12 → central 76 % maps to the full screen).
        Keeps extreme hand positions reachable.  Default 0.12.
    click_cooldown : float
        Minimum seconds between consecutive click events.  Default 0.5.
    scroll_sensitivity : int
        Win32 WHEEL_DELTA units scrolled per 0.1 landmark-unit of vertical
        change.  Default 600  (positive = scroll up).
    """

    # Landmark indexes (MediaPipe Hands)
    _CURSOR_LM = 8   # index tip
    _THUMB_LM  = 4   # thumb tip
    _INDEX_LM  = 8   # index tip

    def __init__(
        self,
        smoothing:          float = 0.25,
        dead_zone:          int   = 4,
        input_margin:       float = 0.12,
        click_cooldown:     float = 0.5,
        scroll_sensitivity: int   = 600,
        pinch_threshold:    float = 0.045,
        pinch_release:      float = 0.065,
    ) -> None:
        _u32 = ctypes.windll.user32
        self._screen_w: int = _u32.GetSystemMetrics(0)
        self._screen_h: int = _u32.GetSystemMetrics(1)

        self._alpha              = max(0.01, min(1.0, smoothing))
        self._dead_zone          = dead_zone
        self._margin             = input_margin
        self._click_cooldown     = click_cooldown
        self._scroll_sensitivity = scroll_sensitivity
        self._pinch_threshold = max(0.01, float(pinch_threshold))
        self._pinch_release_threshold = max(self._pinch_threshold + 0.005, float(pinch_release))

        # Smoothed cursor state
        self._smooth_x: float | None = None
        self._smooth_y: float | None = None

        # Scroll anchor (normalised y of index tip when scroll gesture began)
        self._scroll_ref_y: float | None = None

        # Click rate-limiting
        self._last_click_time: float = 0.0

        # Previous gesture (for edge-detection on click gestures)
        self._prev_gesture: str | None = None
        self._pinch_active = False

        print(
            f'[AirMouseController] Screen {self._screen_w}x{self._screen_h}  '
            f'alpha={self._alpha}  margin={self._margin}  dz={self._dead_zone}px'
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        landmarks:     list[tuple[float, float, float]],
        finger_states: dict,
        gesture:       str | None,
        frame_w:       int,
        frame_h:       int,
    ) -> str | None:
        """
        Process one frame of hand data; move cursor / fire clicks / scroll.

        Parameters
        ----------
        landmarks     : Normalised (x, y, z) tuples, one per landmark (21 total).
        finger_states : Dict from HandTracker  {thumb/index/middle/ring/pinky: bool}.
        gesture       : Classified gesture name, or None.
        frame_w, frame_h : Camera frame pixel dimensions (landmarks are normalised).

        Returns
        -------
        str | None
            Human-readable label of the action taken this frame, or None.
        """
        if not landmarks:
            self._smooth_x     = None
            self._smooth_y     = None
            self._scroll_ref_y = None
            self._pinch_active = False
            self._prev_gesture = gesture
            return None

        action_taken: str | None = None

        # Cursor movement is always driven by index tip in System Mode.
        self._move_cursor(landmarks)

        # Pinch click (thumb + index) with hysteresis and rising-edge trigger.
        pinch_enabled = bool(finger_states and finger_states.get('thumb') and finger_states.get('index'))
        pinch_now = self._update_pinch_state(landmarks) if pinch_enabled else False
        if pinch_now and not self._pinch_active:
            action_taken = self._left_click()
        self._pinch_active = pinch_now

        # Optional legacy gesture actions remain available.
        if action_taken is not None:
            self._prev_gesture = gesture
            return action_taken

        if gesture == 'One Finger':
            self._scroll_ref_y = None

        # ── Scroll (Two Fingers — vertical delta drives wheel) ───────────
        elif gesture == 'Two Fingers':
            action_taken = self._scroll(landmarks)

        # ── Right click (Thumb, Index, Middle and Ring — rising edge) ───
        elif gesture == 'Thumb, Index, Middle and Ring' and self._prev_gesture != 'Thumb, Index, Middle and Ring':
            action_taken = self._right_click()

        # ── Double-click (Thumbs Up — rising edge) ───────────────────────
        elif gesture == 'Thumbs Up' and self._prev_gesture != 'Thumbs Up':
            action_taken = self._double_click()

        else:
            self._scroll_ref_y = None

        self._prev_gesture = gesture
        return action_taken

    def reset(self) -> None:
        """Reset all transient state (call when leaving System Mode)."""
        self._smooth_x     = None
        self._smooth_y     = None
        self._scroll_ref_y = None
        self._prev_gesture = None
        self._pinch_active = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _move_cursor(self, landmarks: list) -> str | None:
        lm = landmarks[self._CURSOR_LM]
        raw_x, raw_y = lm[0], lm[1]

        # Map [margin, 1−margin] → [0, screen_w/h]; clamp to screen edges
        m     = self._margin
        scale = 1.0 - 2.0 * m
        tx = max(0.0, min(float(self._screen_w - 1), (raw_x - m) / scale * self._screen_w))
        ty = max(0.0, min(float(self._screen_h - 1), (raw_y - m) / scale * self._screen_h))

        # EMA smoothing
        if self._smooth_x is None:
            self._smooth_x, self._smooth_y = tx, ty
        else:
            a = self._alpha
            self._smooth_x = a * tx + (1.0 - a) * self._smooth_x
            self._smooth_y = a * ty + (1.0 - a) * self._smooth_y

        sx, sy = int(self._smooth_x), int(self._smooth_y)

        # Dead-zone: compare against current OS cursor position
        cur = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(cur))
        if abs(cur.x - sx) <= self._dead_zone and abs(cur.y - sy) <= self._dead_zone:
            return None

        ctypes.windll.user32.SetCursorPos(sx, sy)
        return None     # continuous movement — suppress per-frame log spam

    def _scroll(self, landmarks: list) -> str | None:
        lm    = landmarks[self._CURSOR_LM]
        cur_y = lm[1]

        if self._scroll_ref_y is None:
            self._scroll_ref_y = cur_y
            return None

        delta_y = self._scroll_ref_y - cur_y   # positive == finger moved up == scroll up
        if abs(delta_y) < 0.01:
            return None

        wheel_units = int(delta_y * self._scroll_sensitivity * 10)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, wheel_units, 0)
        self._scroll_ref_y = cur_y              # shift anchor → relative scroll
        return 'Scroll Up' if wheel_units > 0 else 'Scroll Down'

    def _update_pinch_state(self, landmarks: list) -> bool:
        """Return True when thumb and index fingertips are pinched."""
        if len(landmarks) <= max(self._THUMB_LM, self._INDEX_LM):
            return False

        thumb = landmarks[self._THUMB_LM]
        index = landmarks[self._INDEX_LM]
        dist = self._distance_3d(thumb, index)

        if self._pinch_active:
            return dist <= self._pinch_release_threshold
        return dist <= self._pinch_threshold

    @staticmethod
    def _distance_3d(a, b) -> float:
        dx = float(a[0]) - float(b[0])
        dy = float(a[1]) - float(b[1])
        dz = float(a[2]) - float(b[2])
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def _left_click(self) -> str | None:
        if not self._cooldown_ok():
            return None
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
        self._last_click_time = time.time()
        return 'Left Click'

    def _right_click(self) -> str | None:
        if not self._cooldown_ok():
            return None
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_RIGHTUP,   0, 0, 0, 0)
        self._last_click_time = time.time()
        return 'Right Click'

    def _double_click(self) -> str | None:
        if not self._cooldown_ok():
            return None
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
        time.sleep(_DOUBLE_CLICK_PAUSE_S)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)
        self._last_click_time = time.time()
        return 'Double Click'

    def _cooldown_ok(self) -> bool:
        return (time.time() - self._last_click_time) >= self._click_cooldown


# ---------------------------------------------------------------------------
# ModeEngineResult  (kept for worker_thread compatibility)
# ---------------------------------------------------------------------------

@dataclass
class ModeEngineResult:
    """Return value from SystemModeEngine.process()."""
    action:         str | None = None
    mode_changed:   bool       = False
    current_mode:   str        = 'App Mode'
    is_active:      bool       = False
    in_cooldown:    bool       = False
    mode_stability: float      = 0.0


# ---------------------------------------------------------------------------
# SystemModeEngine  (high-level coordinator — unchanged public interface)
# ---------------------------------------------------------------------------

class SystemModeEngine:
    """
    High-level coordinator that owns DecisionEngine, ActivationManager,
    and AirMouseController.

    The AirMouseController is driven directly by the worker thread via
    the ``air_mouse`` property so it receives raw landmarks every frame.
    """

    MODES        = ('App Mode', 'Media Mode', 'System Mode')
    DEFAULT_MODE = 'App Mode'

    def __init__(
        self,
        open_palm_duration:  float = 2.0,
        cooldown_duration:   float = 1.0,
        stability_threshold: int   = 10,
        config_path:         str | None = None,
    ) -> None:
        from engine.activation_manager import ActivationManager
        from core.decision_engine      import DecisionEngine

        self._activation = ActivationManager(
            open_palm_duration  = open_palm_duration,
            cooldown_duration   = cooldown_duration,
            stability_threshold = stability_threshold,
        )
        self._decision  = DecisionEngine(config_path=config_path)
        self._air_mouse = AirMouseController()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> str:
        """The currently active Smart Mode name."""
        return self._decision.current_mode

    @property
    def is_active(self) -> bool:
        """Whether the system has been activated (Open Palm held)."""
        return self._activation.is_active

    @property
    def in_cooldown(self) -> bool:
        """Whether the system is currently in the action cooldown window."""
        return self._activation.is_in_cooldown

    @property
    def mode_stability_progress(self) -> float:
        """0.0–1.0 hold progress toward a mode switch."""
        return self._decision.mode_stability_progress

    @property
    def air_mouse(self) -> AirMouseController:
        """Direct reference to the AirMouseController for the worker thread."""
        return self._air_mouse

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def process(self, gesture: str | None) -> ModeEngineResult:
        """
        Run one tick for the given gesture string.
        Air-mouse cursor control is NOT applied here — the worker thread
        calls ``air_mouse.update()`` directly with raw landmarks each frame.
        """
        action, mode_changed = self._decision.process(gesture)
        should_execute       = self._activation.update(gesture)
        if not should_execute:
            action = None
        return ModeEngineResult(
            action         = action,
            mode_changed   = mode_changed,
            current_mode   = self._decision.current_mode,
            is_active      = self._activation.is_active,
            in_cooldown    = self._activation.is_in_cooldown,
            mode_stability = self._decision.mode_stability_progress,
        )

    def status_summary(self) -> dict:
        """Return a plain-dict snapshot of the engine state for logging."""
        return {
            'mode':      self.current_mode,
            'active':    self.is_active,
            'cooldown':  self.in_cooldown,
            'stability': round(self.mode_stability_progress, 2),
            'timestamp': datetime.now().strftime('%H:%M:%S'),
        }
