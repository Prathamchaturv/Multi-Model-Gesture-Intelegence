"""
Module: shared_state.py
Description: Central reactive data store for the MMGI PyQt6 dashboard —
             exposes every live pipeline value (fps, mode, gesture, etc.) as
             a typed PyQt6 signal so all UI panels update independently.
Author: Pratham Chaturvedi

ui/shared_state.py - Central reactive state store for the MMGI PyQt6 dashboard.

All live data produced by the worker thread is stored here and exposed as
PyQt6 signals so UI panels can subscribe independently without tight coupling.

Usage
-----
from ui.shared_state import SharedState

state = SharedState()          # one instance shared app-wide
state.system_active_changed.connect(my_slot)
state.set_system_active(True)
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class SharedState(QObject):
    """
    Central reactive data store.

    Fields
    ------
    system_active : bool          – whether MMGI tracking is running
    current_mode  : str           – 'App Mode' | 'Media Mode' | 'System Mode'
    current_gesture: str          – latest recognised gesture name ('' = none)
    confidence    : float         – 0.0 – 1.0 classifier confidence
    fps           : float         – camera frames per second
    latency_ms    : float         – pipeline latency in milliseconds
    in_cooldown   : bool          – True while action/mode cooldown is active
    volume_level  : int           – 0–100 system volume estimate
    mode_stability: float         – 0.0–1.0 mode-switch hold progress
    """

    # ------------------------------------------------------------------ signals
    system_active_changed   = pyqtSignal(bool)
    mode_changed            = pyqtSignal(str)
    gesture_changed         = pyqtSignal(str)
    confidence_changed      = pyqtSignal(float)
    fps_changed             = pyqtSignal(float)
    latency_changed         = pyqtSignal(float)
    cooldown_changed        = pyqtSignal(bool)
    volume_changed          = pyqtSignal(int)
    mode_stability_changed  = pyqtSignal(float)
    landmarks_changed       = pyqtSignal(object)
    face_auth_changed       = pyqtSignal(bool, str)
    voice_command_changed   = pyqtSignal(str)
    cursor_sensitivity_changed = pyqtSignal(float)
    metrics_changed         = pyqtSignal(dict)
    gesture_status_changed  = pyqtSignal(str)
    face_security_enabled_changed = pyqtSignal(bool)
    voice_listener_enabled_changed = pyqtSignal(bool)
    gesture_control_enabled_changed = pyqtSignal(bool)
    mode_request_changed    = pyqtSignal(str)
    activation_lock_changed = pyqtSignal(bool, str)
    fail_safe_state_changed = pyqtSignal(str, str)
    fail_safe_flags_changed = pyqtSignal(dict)

    # Batched update – emits a snapshot dict for panels that want everything
    snapshot_ready          = pyqtSignal(dict)

    # Activity log: (timestamp_str, event_category, description)
    log_event               = pyqtSignal(str, str, str)

    # Fired each time an action is executed (action key string, e.g. 'open_brave')
    action_executed         = pyqtSignal(str)

    # ------------------------------------------------------------------ init
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._system_active    = False
        self._current_mode     = 'App Mode'
        self._current_gesture  = ''
        self._confidence       = 0.0
        self._fps              = 0.0
        self._latency_ms       = 0.0
        self._in_cooldown      = False
        self._volume_level     = 50
        self._mode_stability   = 0.0
        self._last_action      = ''
        self._latest_landmarks = None
        self._face_authorized  = True
        self._face_status      = 'Face Auth: Idle'
        self._voice_command    = ''
        self._cursor_sensitivity = 1.0
        self._metrics = {
            'gesture_accuracy_pct': 0.0,
            'false_activation_rate_pct': 0.0,
            'avg_response_latency_ms': 0.0,
            'mode_switches_per_min': 0.0,
        }
        self._gesture_status = 'Not Detected'
        self._face_security_enabled = True
        self._voice_listener_enabled = True
        self._gesture_control_enabled = True
        self._requested_mode = 'App Mode'
        self._activation_locked = True
        self._activation_lock_reason = 'Waiting for stable gesture'
        self._fail_safe_state = 'READY'
        self._fail_safe_message = 'System ready'
        self._fail_safe_flags = {
            'LOW_CONFIDENCE': False,
            'NO_FACE_DETECTED': False,
            'AUTH_REQUIRED': False,
            'COOLDOWN_ACTIVE': False,
        }

    # ------------------------------------------------------------------ getters
    @property
    def system_active(self)   -> bool:  return self._system_active
    @property
    def current_mode(self)    -> str:   return self._current_mode
    @property
    def current_gesture(self) -> str:   return self._current_gesture
    @property
    def confidence(self)      -> float: return self._confidence
    @property
    def fps(self)             -> float: return self._fps
    @property
    def latency_ms(self)      -> float: return self._latency_ms
    @property
    def in_cooldown(self)     -> bool:  return self._in_cooldown
    @property
    def volume_level(self)    -> int:   return self._volume_level
    @property
    def mode_stability(self)  -> float: return self._mode_stability
    @property
    def face_authorized(self) -> bool:  return self._face_authorized
    @property
    def face_status(self)     -> str:   return self._face_status
    @property
    def voice_command(self)   -> str:   return self._voice_command
    @property
    def cursor_sensitivity(self) -> float: return self._cursor_sensitivity
    @property
    def metrics(self) -> dict: return dict(self._metrics)
    @property
    def gesture_status(self) -> str: return self._gesture_status
    @property
    def face_security_enabled(self) -> bool: return self._face_security_enabled
    @property
    def voice_listener_enabled(self) -> bool: return self._voice_listener_enabled
    @property
    def gesture_control_enabled(self) -> bool: return self._gesture_control_enabled
    @property
    def requested_mode(self) -> str: return self._requested_mode
    @property
    def activation_locked(self) -> bool: return self._activation_locked
    @property
    def activation_lock_reason(self) -> str: return self._activation_lock_reason
    @property
    def fail_safe_state(self) -> str: return self._fail_safe_state
    @property
    def fail_safe_message(self) -> str: return self._fail_safe_message
    @property
    def fail_safe_flags(self) -> dict: return dict(self._fail_safe_flags)

    # ------------------------------------------------------------------ setters
    def set_system_active(self, value: bool) -> None:
        if self._system_active != value:
            self._system_active = value
            self.system_active_changed.emit(value)
            self._emit_snapshot()

    def set_mode(self, value: str) -> None:
        if self._current_mode != value:
            self._current_mode = value
            self.mode_changed.emit(value)
            self._emit_snapshot()

    def set_gesture(self, value: str) -> None:
        if self._current_gesture != value:
            self._current_gesture = value
            self.gesture_changed.emit(value)

    def set_confidence(self, value: float) -> None:
        self._confidence = round(value, 3)
        self.confidence_changed.emit(self._confidence)

    def set_fps(self, value: float) -> None:
        self._fps = round(value, 1)
        self.fps_changed.emit(self._fps)

    def set_latency(self, value: float) -> None:
        self._latency_ms = round(value, 1)
        self.latency_changed.emit(self._latency_ms)

    def set_cooldown(self, value: bool) -> None:
        if self._in_cooldown != value:
            self._in_cooldown = value
            self.cooldown_changed.emit(value)

    def set_volume(self, value: int) -> None:
        clamped = max(0, min(100, value))
        if self._volume_level != clamped:
            self._volume_level = clamped
            self.volume_changed.emit(clamped)

    def set_mode_stability(self, value: float) -> None:
        self._mode_stability = round(max(0.0, min(1.0, value)), 3)
        self.mode_stability_changed.emit(self._mode_stability)

    def set_action_executed(self, action: str) -> None:
        """Record the most recently executed action and broadcast it."""
        self._last_action = action
        self.action_executed.emit(action)

    def set_landmarks(self, landmarks) -> None:
        """Broadcast latest 21-point landmarks (or None when no hand)."""
        self._latest_landmarks = landmarks
        self.landmarks_changed.emit(landmarks)

    def set_face_auth(self, authorized: bool, status_text: str) -> None:
        """Broadcast current face authorization state."""
        changed = (
            self._face_authorized != bool(authorized)
            or self._face_status != str(status_text)
        )
        self._face_authorized = bool(authorized)
        self._face_status = str(status_text)
        if changed:
            self.face_auth_changed.emit(self._face_authorized, self._face_status)

    def set_voice_command(self, command_text: str) -> None:
        """Broadcast latest recognized voice command."""
        value = str(command_text)
        if self._voice_command != value:
            self._voice_command = value
            self.voice_command_changed.emit(value)

    def set_gesture_status(self, value: str) -> None:
        """Broadcast gesture verification status for runtime/debug UI."""
        status = str(value)
        if self._gesture_status != status:
            self._gesture_status = status
            self.gesture_status_changed.emit(status)

    def set_face_security_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._face_security_enabled != value:
            self._face_security_enabled = value
            self.face_security_enabled_changed.emit(value)

    def set_voice_listener_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._voice_listener_enabled != value:
            self._voice_listener_enabled = value
            self.voice_listener_enabled_changed.emit(value)

    def set_gesture_control_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._gesture_control_enabled != value:
            self._gesture_control_enabled = value
            self.gesture_control_enabled_changed.emit(value)

    def request_mode(self, mode: str) -> None:
        value = str(mode)
        if self._requested_mode != value:
            self._requested_mode = value
            self.mode_request_changed.emit(value)

    def set_activation_lock(self, locked: bool, reason: str) -> None:
        new_locked = bool(locked)
        new_reason = str(reason)
        changed = new_locked != self._activation_locked or new_reason != self._activation_lock_reason
        self._activation_locked = new_locked
        self._activation_lock_reason = new_reason
        if changed:
            self.activation_lock_changed.emit(new_locked, new_reason)

    def set_cursor_sensitivity(self, value: float) -> None:
        """Broadcast dynamic cursor sensitivity from calibration policy."""
        clamped = round(max(0.1, min(3.0, float(value))), 2)
        if self._cursor_sensitivity != clamped:
            self._cursor_sensitivity = clamped
            self.cursor_sensitivity_changed.emit(clamped)

    def set_fail_safe_states(
        self,
        *,
        low_confidence: bool = False,
        no_face_detected: bool = False,
        auth_required: bool = False,
        cooldown_active: bool = False,
    ) -> None:
        """Update fail-safe flags and broadcast the dominant user-facing safety state."""
        new_flags = {
            'LOW_CONFIDENCE': bool(low_confidence),
            'NO_FACE_DETECTED': bool(no_face_detected),
            'AUTH_REQUIRED': bool(auth_required),
            'COOLDOWN_ACTIVE': bool(cooldown_active),
        }
        if new_flags != self._fail_safe_flags:
            self._fail_safe_flags = new_flags
            self.fail_safe_flags_changed.emit(dict(new_flags))

        # Priority: authorization and detection blocks first, then cooldown, then confidence.
        if new_flags['AUTH_REQUIRED']:
            state_key = 'AUTH_REQUIRED'
            message = 'Face authorization required - access blocked'
        elif new_flags['NO_FACE_DETECTED']:
            state_key = 'NO_FACE_DETECTED'
            message = 'Face not detected - access blocked'
        elif new_flags['COOLDOWN_ACTIVE']:
            state_key = 'COOLDOWN_ACTIVE'
            message = 'Cooldown active - wait before next action'
        elif new_flags['LOW_CONFIDENCE']:
            state_key = 'LOW_CONFIDENCE'
            message = 'Low confidence - retry gesture'
        else:
            state_key = 'READY'
            message = 'System ready'

        if state_key != self._fail_safe_state or message != self._fail_safe_message:
            self._fail_safe_state = state_key
            self._fail_safe_message = message
            self.fail_safe_state_changed.emit(state_key, message)

    def set_metrics(self, metrics: dict) -> None:
        """Broadcast latest lightweight performance metrics."""
        payload = {
            'gesture_accuracy_pct': float(metrics.get('gesture_accuracy_pct', 0.0)),
            'false_activation_rate_pct': float(metrics.get('false_activation_rate_pct', 0.0)),
            'avg_response_latency_ms': float(metrics.get('avg_response_latency_ms', 0.0)),
            'mode_switches_per_min': float(metrics.get('mode_switches_per_min', 0.0)),
        }
        self._metrics = payload
        self.metrics_changed.emit(dict(payload))

    def emit_log(self, timestamp: str, category: str, description: str) -> None:
        """Convenience wrapper to push an activity log event."""
        self.log_event.emit(timestamp, category, description)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self) -> dict:
        """Return all current values as a plain dict."""
        return {
            'system_active':  self._system_active,
            'current_mode':   self._current_mode,
            'current_gesture':self._current_gesture,
            'confidence':     self._confidence,
            'fps':            self._fps,
            'latency_ms':     self._latency_ms,
            'in_cooldown':    self._in_cooldown,
            'volume_level':   self._volume_level,
            'mode_stability': self._mode_stability,
            'face_authorized': self._face_authorized,
            'face_status': self._face_status,
            'voice_command': self._voice_command,
            'cursor_sensitivity': self._cursor_sensitivity,
            'metrics': dict(self._metrics),
            'gesture_status': self._gesture_status,
            'face_security_enabled': self._face_security_enabled,
            'voice_listener_enabled': self._voice_listener_enabled,
            'gesture_control_enabled': self._gesture_control_enabled,
            'requested_mode': self._requested_mode,
            'activation_locked': self._activation_locked,
            'activation_lock_reason': self._activation_lock_reason,
            'fail_safe_state': self._fail_safe_state,
            'fail_safe_message': self._fail_safe_message,
            'fail_safe_flags': dict(self._fail_safe_flags),
        }

    def _emit_snapshot(self) -> None:
        self.snapshot_ready.emit(self.snapshot())
