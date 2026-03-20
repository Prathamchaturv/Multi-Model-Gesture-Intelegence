"""
Module: worker_thread.py
Description: Background QThread that owns the full per-frame gesture pipeline
             — reads camera frames, runs AI inference, resolves actions, drives
             the Air Mouse, and emits QImage frames to the dashboard.
Author: Pratham Chaturvedi

ui/worker_thread.py - MMGI Pipeline Worker (QThread)

Runs the full gesture recognition pipeline in a background thread and
pushes state updates into SharedState so the UI never blocks.

Pipeline per frame
------------------
1. Camera.read_frame()
2. HandTracker.process_frame()
3. GestureClassifier.classify()
4. DecisionEngine.process()  ← Smart Mode (mode-switch OR action)
5. ActivationManager.update()
6. ActionExecutor.execute()   (only when active + action resolved)
7. Update SharedState + emit frame as QImage

Signals emitted to the outside
-------------------------------
frame_ready(QImage)  – annotated video frame for the Vision Panel
error(str)           – fatal pipeline error message
"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
from PyQt6.QtCore  import QThread, pyqtSignal
from PyQt6.QtGui   import QImage

from core.camera                 import Camera
from core.hand_tracking          import HandTracker
from core.gesture_classifier     import GestureClassifier
from core.adaptive_gesture_learning import (
    AdaptiveGestureMatcher,
    CustomGestureStore,
    MultiFrameGestureConfirmation,
)
from core.face_security          import FaceSecurityManager
from core.voice_control          import VoiceCommandListener
from core.system_mode_engine     import AirMouseController
from engine.activation_manager   import ActivationManager
from engine.decision_engine      import DecisionEngine
from engine.multimodal_fusion    import MultiModalFusionEngine
from engine.action_executor      import ActionExecutor
from utils.fps_counter           import FPSCounter
from utils.config                import Config
from utils.logger                import (
    get_mmgi_logger,
    log_action_executed,
    log_gesture_detected,
    log_low_confidence,
    log_pipeline_state,
    log_runtime_error,
)
from ui.shared_state             import SharedState


# ---------------------------------------------------------------------------
# Overlay helpers
# ---------------------------------------------------------------------------

_ACCENT   = (0, 229, 255)   # #00E5FF  (BGR)
_GREEN    = (0, 255, 136)   # #00FF88
_RED      = (70, 68, 255)   # #FF4466
_WHITE    = (255, 255, 255)
_DARK     = (20, 20, 30)

_MODE_COLOURS = {
    'App Mode':    (0, 229, 255),    # cyan
    'Media Mode':  (0, 200, 255),    # sky
    'System Mode': (120, 100, 255),  # violet
}


class GestureStabilityFilter:
    """Smooth raw frame-wise gestures into stable confirmed gestures."""

    def __init__(
        self,
        confirm_frames: int = 4,
        min_switch_interval_s: float = 0.25,
    ) -> None:
        self._confirm_frames = max(3, int(confirm_frames))
        self._min_switch_interval_s = float(min_switch_interval_s)
        self._recent: deque[str] = deque(maxlen=self._confirm_frames)
        self._last_confirmed: str | None = None
        self._last_confirmed_change_ts: float = 0.0

    def update(self, raw_gesture: str | None, hand_present: bool) -> tuple[str | None, str]:
        """
        Returns:
            (confirmed_gesture, status)
            status in {'stable', 'unclear', 'no_hand'}
        """
        if not hand_present:
            self._recent.clear()
            self._last_confirmed = None
            return None, 'no_hand'

        if not raw_gesture:
            self._recent.clear()
            self._last_confirmed = None
            return None, 'unclear'

        self._recent.append(raw_gesture)
        if len(self._recent) < self._confirm_frames:
            return None, 'unclear'

        if len(set(self._recent)) != 1:
            return None, 'unclear'

        candidate = self._recent[-1]
        now = time.time()

        # Debounce rapid switches between different gestures.
        if self._last_confirmed and candidate != self._last_confirmed:
            if now - self._last_confirmed_change_ts < self._min_switch_interval_s:
                return None, 'unclear'

        if candidate != self._last_confirmed:
            self._last_confirmed = candidate
            self._last_confirmed_change_ts = now

        return candidate, 'stable'

def _ts() -> str:
    return datetime.now().strftime('%H:%M:%S')


def _load_face_security_settings(config: Config) -> dict:
    """Load face-security settings from config/face_security.json when present."""
    settings = {
        'enabled': bool(config.get('face_security.enabled', True)),
        'authorized_image_path': str(config.get('face_security.authorized_image_path', 'config/authorized_face.jpg')),
        'authorized_encoding_path': str(config.get('face_security.authorized_encoding_path', 'config/authorized_face_encoding.json')),
        'similarity_threshold': float(config.get('face_security.similarity_threshold', 0.84)),
        'min_detection_confidence': float(config.get('face_security.min_detection_confidence', 0.6)),
        'eval_interval_s': float(config.get('face_security.eval_interval_s', 0.08)),
        'away_delay_s': float(config.get('face_security.away_delay_s', 2.5)),
        'return_confirm_s': float(config.get('face_security.return_confirm_s', 0.7)),
    }
    path = Path(__file__).parent.parent / 'config' / 'face_security.json'
    if not path.exists():
        return settings

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
    except Exception:
        return settings

    if isinstance(raw, dict):
        settings.update(raw)
    return settings


def _load_voice_control_settings(config: Config) -> dict:
    """Load voice-control settings from config/voice_control.json when present."""
    settings = {
        'enabled': bool(config.get('voice_control.enabled', True)),
        'listen_timeout_s': float(config.get('voice_control.listen_timeout_s', 1.2)),
        'phrase_time_limit_s': float(config.get('voice_control.phrase_time_limit_s', 2.0)),
        'energy_threshold': int(config.get('voice_control.energy_threshold', 250)),
        'fusion_command_ttl_s': float(config.get('voice_control.fusion_command_ttl_s', 2.5)),
        'required_actions': list(config.get('voice_control.required_actions', ['play_pause', 'mute'])),
        'action_voice_map': dict(config.get('voice_control.action_voice_map', {
            'play_pause': ['play_song', 'pause'],
            'mute': ['mute'],
            'next_track': ['next_track'],
            'prev_track': ['previous_track'],
            'volume_up': ['volume_up'],
            'volume_down': ['volume_down'],
        })),
    }

    path = Path(__file__).parent.parent / 'config' / 'voice_control.json'
    if not path.exists():
        return settings

    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
    except Exception:
        return settings

    if isinstance(raw, dict):
        settings.update(raw)
    return settings


def _voice_label(command: str) -> str:
    labels = {
        'play_song': 'Play Song',
        'pause': 'Pause',
        'next_track': 'Next Track',
        'previous_track': 'Previous Track',
        'volume_up': 'Volume Up',
        'volume_down': 'Volume Down',
        'mute': 'Mute',
    }
    return labels.get(command, command)


def _draw_overlay(
    frame,
    gesture: str | None,
    mode: str,
    is_active: bool,
    fps: float,
    face_status: str | None = None,
    face_authorized: bool | None = None,
) -> None:
    """Annotate frame in-place with gesture/mode/state HUD."""
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 60), _DARK, -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # State indicator
    state_color = _GREEN if is_active else _RED
    state_text  = 'ACTIVE' if is_active else 'INACTIVE'
    cv2.circle(frame, (24, 30), 8, state_color, -1)
    cv2.putText(frame, state_text, (38, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, state_color, 2)

    # Mode
    mc = _MODE_COLOURS.get(mode, _ACCENT)
    cv2.putText(frame, mode.upper(), (w // 2 - 70, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, mc, 2)

    # FPS
    cv2.putText(frame, f'FPS {fps:.0f}', (w - 90, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, _WHITE, 1)

    if face_status:
        face_colour = _GREEN if face_authorized else _RED
        cv2.putText(
            frame,
            face_status,
            (16, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            face_colour,
            1,
        )

    # Gesture label
    if gesture:
        cv2.putText(frame, gesture, (16, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, _ACCENT, 2)


def _frame_to_qimage(frame) -> QImage:
    """Convert a BGR numpy frame to QImage (RGB888)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()


# ---------------------------------------------------------------------------
# Worker Thread
# ---------------------------------------------------------------------------

class WorkerThread(QThread):
    """Background pipeline thread."""

    frame_ready = pyqtSignal(QImage)
    error       = pyqtSignal(str)

    def __init__(self, state: SharedState, parent=None) -> None:
        super().__init__(parent)
        self._state   = state
        self._running = False

        # Pipeline components (created in run() so they start on the right thread)
        self._config:    Config | None = None
        self._camera:    Camera | None = None

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Request the pipeline to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: C901  (unavoidably long entry point)
        self._running = True
        state = self._state
        camera: Camera | None = None
        face_security: FaceSecurityManager | None = None
        voice_listener: VoiceCommandListener | None = None

        try:
            config = Config()
            get_mmgi_logger()  # ensure logger is initialized once on worker start
            low_conf_threshold = float(config.get('hand_tracking.min_detection_confidence'))

            face_cfg = _load_face_security_settings(config)
            face_security = FaceSecurityManager(
                enabled=bool(face_cfg.get('enabled', True)),
                authorized_image_path=str(face_cfg.get('authorized_image_path', 'config/authorized_face.jpg')),
                authorized_encoding_path=str(face_cfg.get('authorized_encoding_path', 'config/authorized_face_encoding.json')),
                similarity_threshold=float(face_cfg.get('similarity_threshold', 0.84)),
                min_detection_confidence=float(face_cfg.get('min_detection_confidence', 0.6)),
                eval_interval_s=float(face_cfg.get('eval_interval_s', 0.08)),
                away_delay_s=float(face_cfg.get('away_delay_s', 2.5)),
                return_confirm_s=float(face_cfg.get('return_confirm_s', 0.7)),
            )

            voice_cfg = _load_voice_control_settings(config)
            voice_listener = VoiceCommandListener(
                enabled=bool(voice_cfg.get('enabled', True)),
                listen_timeout_s=float(voice_cfg.get('listen_timeout_s', 1.2)),
                phrase_time_limit_s=float(voice_cfg.get('phrase_time_limit_s', 2.0)),
                energy_threshold=int(voice_cfg.get('energy_threshold', 250)),
            )
            voice_enabled_for_fusion = voice_listener.is_enabled
            fusion_engine = MultiModalFusionEngine(
                required_actions=(
                    {str(x) for x in list(voice_cfg.get('required_actions', ['play_pause', 'mute']))}
                    if voice_enabled_for_fusion
                    else set()
                ),
                action_voice_map={
                    str(k): {str(vv) for vv in vals}
                    for k, vals in dict(voice_cfg.get('action_voice_map', {})).items()
                },
                command_ttl_s=float(voice_cfg.get('fusion_command_ttl_s', 2.5)),
            )
            voice_listener.start()
            state.set_voice_command('Listening...' if voice_enabled_for_fusion else 'Voice Unavailable')

            camera = Camera(
                width  = config.get('camera.width'),
                height = config.get('camera.height'),
                fps    = config.get('camera.fps'),
            )
            if not camera.open():
                self.error.emit('Could not open camera.')
                return

            hand_tracker = HandTracker(
                max_num_hands            = config.get('hand_tracking.max_num_hands'),
                min_detection_confidence = config.get('hand_tracking.min_detection_confidence'),
                min_tracking_confidence  = config.get('hand_tracking.min_tracking_confidence'),
            )

            gesture_classifier = GestureClassifier()
            adaptive_enabled = bool(config.get('adaptive_gesture.enabled', True))
            custom_matcher: AdaptiveGestureMatcher | None = None
            custom_confirmation: MultiFrameGestureConfirmation | None = None

            if adaptive_enabled:
                configured_store_path = str(config.get('adaptive_gesture.store_path') or 'config/custom_gestures.json')
                resolved_store_path = Path(configured_store_path)
                if not resolved_store_path.is_absolute():
                    resolved_store_path = Path(__file__).parent.parent / resolved_store_path

                custom_store = CustomGestureStore(resolved_store_path)
                custom_matcher = AdaptiveGestureMatcher(
                    store=custom_store,
                    threshold=float(config.get('adaptive_gesture.match_threshold') or 0.12),
                )
                custom_confirmation = MultiFrameGestureConfirmation(
                    confirm_frames=int(config.get('adaptive_gesture.confirm_frames') or 4)
                )

            activation_manager = ActivationManager(
                open_palm_duration   = config.get('activation.open_palm_duration'),
                cooldown_duration    = config.get('activation.cooldown_duration'),
                stability_threshold  = config.get('activation.stability_threshold'),
            )

            decision_engine = DecisionEngine()

            action_executor = ActionExecutor(config={
                'brave_path':        config.get('apps.brave_path'),
                'apple_music_aumid': config.get('apps.apple_music_aumid'),
            })

            air_mouse   = AirMouseController()
            _prev_mode  = decision_engine.current_mode
            fps_counter = FPSCounter()
            gesture_filter = GestureStabilityFilter(confirm_frames=4, min_switch_interval_s=0.25)
            last_logged_gesture: str | None = None
            last_no_hand_log = 0.0
            last_low_conf_log = 0.0
            last_invalid_log = 0.0

            warning_interval = 1.5
            error_interval = 1.5
            last_face_authorized: bool | None = None
            was_active_before_away = False
            last_presence_paused: bool | None = None

            state.emit_log(_ts(), 'SYSTEM', 'Pipeline started — show Open Palm to activate')
            log_pipeline_state('Pipeline started')
            state.set_face_auth(True, 'Face Auth: Idle (System Mode Only)')

            # ----------------------------------------------------------------
            # Frame loop
            # ----------------------------------------------------------------
            while self._running:
                t_start = time.perf_counter()

                ok, frame = camera.read_frame()
                if not ok or frame is None:
                    continue

                # Mirror for natural interaction
                frame = cv2.flip(frame, 1)

                # ----------------------------------------------------------
                # Voice command polling (non-blocking)
                # ----------------------------------------------------------
                if voice_listener is not None:
                    voice_event = voice_listener.poll_latest()
                    if voice_event is not None:
                        fusion_engine.update_voice(voice_event.command, ts=voice_event.timestamp)
                        voice_text = _voice_label(voice_event.command)
                        state.set_voice_command(voice_text)
                        state.emit_log(_ts(), 'ACTION', f'Voice command detected: {voice_text}')

                # ----------------------------------------------------------
                # System Mode presence + face-security gate (early)
                # ----------------------------------------------------------
                face_authorized = True
                face_status = 'Face Auth: Idle (System Mode Only)'
                user_away = False
                mode_is_system = decision_engine.current_mode == 'System Mode'
                if mode_is_system and face_security is not None:
                    auth_result = face_security.evaluate(frame)
                    face_authorized = auth_result.is_authorized
                    face_status = auth_result.status_text
                    user_away = auth_result.system_paused
                    state.set_face_auth(face_authorized, face_status)

                    if last_face_authorized is None or face_authorized != last_face_authorized:
                        if face_authorized:
                            state.emit_log(_ts(), 'SYSTEM', 'User Recognized — System Unlocked')
                        else:
                            state.emit_log(_ts(), 'ERROR', 'Unknown User — System Locked')
                        last_face_authorized = face_authorized

                    if last_presence_paused is None or user_away != last_presence_paused:
                        if user_away:
                            state.emit_log(_ts(), 'SYSTEM', 'User Away - System Paused')
                        else:
                            state.emit_log(_ts(), 'SYSTEM', 'User Detected - System Active')
                        last_presence_paused = user_away
                else:
                    state.set_face_auth(True, face_status)
                    last_face_authorized = None
                    last_presence_paused = None

                # ----------------------------------------------------------
                # Hand detection + gesture classification
                # ----------------------------------------------------------
                skip_hand_processing = mode_is_system and user_away
                detection_result = None
                hands_info = {}
                if not skip_hand_processing:
                    detection_result = hand_tracker.detect_hands(frame)
                    hands_info = hand_tracker.get_hands_info(detection_result)

                gesture: str | None = None
                confidence          = 0.0
                ui_gesture_text = 'Gesture unclear'
                custom_match = None
                custom_action: str | None = None

                # Prefer right hand; fall back to left
                hand_data = hands_info.get('right') or hands_info.get('left')
                if hand_data:
                    state.set_landmarks(hand_data.get('landmarks'))
                    confidence = float(hand_data.get('confidence', 0.0))

                    if confidence < low_conf_threshold:
                        gesture, _ = gesture_filter.update(None, hand_present=True)
                        ui_gesture_text = 'Gesture unclear'
                        last_logged_gesture = None
                        now = time.time()
                        if now - last_low_conf_log >= warning_interval:
                            log_low_confidence(confidence)
                            last_low_conf_log = now
                    else:
                        if adaptive_enabled and custom_matcher is not None and custom_confirmation is not None:
                            custom_match = custom_matcher.match(hand_data.get('landmarks'))
                            confirmed_name = custom_confirmation.update(
                                custom_match.name if custom_match is not None else None
                            )
                            if confirmed_name and custom_match is not None and custom_match.name == confirmed_name:
                                gesture = f'Custom: {custom_match.name}'
                                custom_action = custom_match.action
                                ui_gesture_text = gesture
                                if gesture != last_logged_gesture:
                                    log_gesture_detected(gesture)
                                    last_logged_gesture = gesture
                            else:
                                custom_action = None

                        if custom_action is None:
                            finger_states = hand_data['finger_states']
                            raw_gesture = gesture_classifier.classify(finger_states)
                            if raw_gesture == 'Unknown':
                                gesture, _ = gesture_filter.update(None, hand_present=True)
                                ui_gesture_text = 'Gesture unclear'
                                last_logged_gesture = None
                                now = time.time()
                                if now - last_invalid_log >= error_interval:
                                    log_runtime_error('Invalid gesture detected')
                                    last_invalid_log = now
                            else:
                                gesture, stable_state = gesture_filter.update(raw_gesture, hand_present=True)
                                if stable_state == 'stable' and gesture is not None:
                                    ui_gesture_text = gesture
                                    if gesture != last_logged_gesture:
                                        log_gesture_detected(gesture)
                                        last_logged_gesture = gesture
                                else:
                                    ui_gesture_text = 'Gesture unclear'
                                    last_logged_gesture = None
                        else:
                            # Keep the predefined gesture filter clean while custom is active.
                            gesture_filter.update(None, hand_present=True)

                    # Draw hand skeleton
                    if detection_result is not None:
                        hand_tracker.draw_landmarks(frame, detection_result)
                else:
                    gesture, _ = gesture_filter.update(None, hand_present=False)
                    state.set_landmarks(None)
                    if custom_confirmation is not None:
                        custom_confirmation.reset()
                    ui_gesture_text = 'User Away - System Paused' if skip_hand_processing else 'No hand detected'
                    now = time.time()
                    if (not skip_hand_processing) and now - last_no_hand_log >= error_interval:
                        log_runtime_error('No hand detected')
                        last_no_hand_log = now
                    last_logged_gesture = None

                # ----------------------------------------------------------
                # Smart Mode decision
                # ----------------------------------------------------------
                if custom_action:
                    # Custom gestures have priority over predefined resolution.
                    decision_engine.process(None)
                    action, mode_changed = custom_action, False
                else:
                    action, mode_changed = decision_engine.process(gesture)

                if mode_changed:
                    new_mode = decision_engine.current_mode
                    state.set_mode(new_mode)
                    state.emit_log(_ts(), 'MODE', f'Switched to {new_mode}')
                    # Reset air mouse when leaving System Mode
                    if _prev_mode == 'System Mode' and new_mode != 'System Mode':
                        air_mouse.reset()
                    _prev_mode = new_mode

                # Mode-switch stability bar
                state.set_mode_stability(decision_engine.mode_stability_progress)

                # ----------------------------------------------------------
                # Activation manager
                # ----------------------------------------------------------
                if decision_engine.current_mode == 'System Mode' and (user_away or not face_authorized):
                    if user_away and activation_manager.is_active:
                        was_active_before_away = True
                    activation_manager.force_inactive(
                        'User away in System Mode' if user_away else 'Unknown user in System Mode'
                    )
                    should_execute = False
                else:
                    if decision_engine.current_mode == 'System Mode' and was_active_before_away:
                        activation_manager.force_active('User returned')
                        was_active_before_away = False
                    should_execute = activation_manager.update(gesture)
                state.set_system_active(activation_manager.is_active)
                state.set_cooldown(activation_manager.is_in_cooldown)

                # ----------------------------------------------------------
                # Execute action  (System Mode → air mouse; others → executor)
                # ----------------------------------------------------------
                if should_execute and custom_action:
                    action_executor.execute(custom_action)
                    label = action_executor._LABELS.get(custom_action, custom_action)
                    state.emit_log(_ts(), 'ACTION', f'{label}  [Custom Gesture]')
                    state.set_action_executed(custom_action)
                    log_action_executed(label)
                elif (
                    decision_engine.current_mode == 'System Mode'
                    and activation_manager.is_active
                    and face_authorized
                ):
                    if hand_data:
                        am_label = air_mouse.update(
                            landmarks     = hand_data['landmarks'],
                            finger_states = hand_data['finger_states'],
                            gesture       = gesture,
                            frame_w       = frame.shape[1],
                            frame_h       = frame.shape[0],
                        )
                        if am_label:
                            state.emit_log(_ts(), 'ACTION', f'{am_label}  [System Mode]')
                            log_action_executed(am_label)
                elif should_execute and action:
                    allow_action = True
                    matched_voice: str | None = None
                    if decision_engine.current_mode == 'Media Mode':
                        allow_action, matched_voice = fusion_engine.resolve(
                            action=action,
                            mode=decision_engine.current_mode,
                        )

                    if allow_action:
                        action_executor.execute(action)
                        label = action_executor._LABELS.get(action, action)
                        if matched_voice:
                            voice_label = _voice_label(matched_voice)
                            state.emit_log(_ts(), 'ACTION', f'{label}  [Media Mode + Voice: {voice_label}]')
                        else:
                            state.emit_log(_ts(), 'ACTION', f'{label}  [{decision_engine.current_mode}]')
                        state.set_action_executed(action)
                        log_action_executed(label)

                # ----------------------------------------------------------
                # Update telemetry
                # ----------------------------------------------------------
                fps_counter.update()
                latency_ms = (time.perf_counter() - t_start) * 1000

                state.set_gesture(ui_gesture_text)
                state.set_confidence(confidence)
                state.set_fps(fps_counter.fps)
                state.set_latency(latency_ms)

                # ----------------------------------------------------------
                # Annotate and emit frame
                # ----------------------------------------------------------
                _draw_overlay(
                    frame,
                    gesture,
                    decision_engine.current_mode,
                    activation_manager.is_active,
                    fps_counter.fps,
                    face_status=face_status if decision_engine.current_mode == 'System Mode' else None,
                    face_authorized=face_authorized if decision_engine.current_mode == 'System Mode' else None,
                )

                self.frame_ready.emit(_frame_to_qimage(frame))

            # ---- Loop exited cleanly ---
            camera.release()
            hand_tracker.close()
            if face_security is not None:
                face_security.close()
            if voice_listener is not None:
                voice_listener.stop()
            state.set_system_active(False)
            state.emit_log(_ts(), 'SYSTEM', 'Pipeline stopped')
            log_pipeline_state('Pipeline stopped')

        except Exception as exc:
            import traceback
            msg = f'Pipeline error: {exc}\n{traceback.format_exc()}'
            self.error.emit(msg)
            try:
                log_runtime_error(f'Pipeline error: {exc}')
            except Exception:
                pass
            try:
                if camera is not None:
                    camera.release()
            except Exception:
                pass
            try:
                if face_security is not None:
                    face_security.close()
            except Exception:
                pass
            try:
                if voice_listener is not None:
                    voice_listener.stop()
            except Exception:
                pass
