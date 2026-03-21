"""
Module: worker_thread.py
Description: Background QThread that owns the full per-frame gesture pipeline
             — reads camera frames, runs AI inference, resolves actions, and
             emits QImage frames to the dashboard.
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
import threading
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
from core.calibration            import CalibrationManager
from core.face_security          import FaceSecurityManager
from core.voice_control          import VoiceCommandListener
from engine.activation_manager   import ActivationManager
from engine.decision_engine      import DecisionEngine
from engine.action_executor      import ActionExecutor
from engine.metrics_manager      import MetricsManager
from engine.multimodal_fusion    import MultimodalFusionLayer
from engine.unified_pipeline     import (
    InputEventNormalizer,
    ModeManager,
    UnifiedDecisionPipeline,
)
from utils.fps_counter           import FPSCounter
from utils.config                import Config
from utils.logger                import (
    get_mmgi_logger,
    log_action_executed,
    log_face_authorization_event,
    log_gesture_detected,
    log_lifecycle_event,
    log_low_confidence,
    log_pipeline_state,
    log_runtime_error,
    log_voice_command_event,
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

    def set_confirm_frames(self, confirm_frames: int) -> None:
        """Apply a new confirmation frame window without restarting the worker."""
        self._confirm_frames = max(3, int(confirm_frames))
        self._recent = deque(maxlen=self._confirm_frames)
        self._last_confirmed = None

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


def _load_voice_control_settings(config: Config) -> dict:
    """Load voice-control settings from config/voice_control.json when present."""
    settings = {
        'enabled': bool(config.get('voice_control.enabled', True)),
        'listen_timeout_s': float(config.get('voice_control.listen_timeout_s', 1.2)),
        'phrase_time_limit_s': float(config.get('voice_control.phrase_time_limit_s', 2.0)),
        'energy_threshold': int(config.get('voice_control.energy_threshold', 250)),
        'recognition_language': str(config.get('voice_control.recognition_language', 'en-IN')),
        'system_mode_only': bool(config.get('voice_control.system_mode_only', True)),
        'system_mode_voice_actions': dict(config.get('voice_control.system_mode_voice_actions', {
            'open_brave': 'open_brave',
            'open_apple_music': 'open_apple_music',
            'open_youtube': 'open_youtube',
            'close_window': 'close_window',
            'switch_tab': 'switch_tab',
            'scroll_down': 'scroll_down',
            'play_song': 'play_pause',
            'pause': 'play_pause',
            'next_track': 'next_track',
            'previous_track': 'prev_track',
            'volume_up': 'volume_up',
            'volume_down': 'volume_down',
            'mute': 'mute',
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


def _load_face_security_settings(config: Config) -> dict:
    """Load face-security runtime settings from config/face_security.json."""
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


def _voice_label(command: str) -> str:
    labels = {
        'open_brave': 'Open Brave',
        'open_apple_music': 'Open Apple Music',
        'open_youtube': 'Open YouTube',
        'close_window': 'Close Window',
        'switch_tab': 'Switch Tab',
        'scroll_down': 'Scroll Down',
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
    debug_text: str | None = None,
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

    if debug_text:
        cv2.putText(
            frame,
            debug_text,
            (16, h - 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            _WHITE,
            1,
        )


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
        self._frame_lock = threading.Lock()
        self._latest_frame_bgr = None
        self._settings_lock = threading.Lock()
        self._reload_calibration_requested = False

        # Pipeline components (created in run() so they start on the right thread)
        self._config:    Config | None = None
        self._camera:    Camera | None = None

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Request the pipeline to stop."""
        self._running = False

    def reload_calibration(self) -> None:
        """Request a hot reload of calibration settings on the worker thread."""
        with self._settings_lock:
            self._reload_calibration_requested = True

    def capture_authorized_face(self) -> tuple[bool, str]:
        """Capture the latest camera face and save it as authorized reference image."""
        with self._frame_lock:
            if self._latest_frame_bgr is None:
                return False, 'No camera frame available yet. Please wait a moment and try again.'
            frame = self._latest_frame_bgr.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade_path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(str(cascade_path))
        if face_cascade.empty():
            return False, 'Face detector unavailable in this environment.'

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(40, 40),
        )
        if len(faces) == 0:
            return False, 'No face detected. Position your face clearly in camera and try again.'

        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        pad = int(min(w, h) * 0.18)
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(frame.shape[1], x + w + pad)
        y2 = min(frame.shape[0], y + h + pad)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return False, 'Face crop failed. Please try again.'

        root = Path(__file__).parent.parent
        img_path = root / 'config' / 'authorized_face.jpg'
        enc_path = root / 'config' / 'authorized_face_encoding.json'
        img_path.parent.mkdir(parents=True, exist_ok=True)

        ok = cv2.imwrite(str(img_path), roi)
        if not ok:
            return False, 'Failed to save authorized face image.'

        # Force encoding regeneration on next startup.
        if enc_path.exists():
            try:
                enc_path.unlink()
            except Exception:
                pass

        return True, 'Authorized face captured. Restart MMGI to activate face security with new enrollment.'

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:  # noqa: C901  (unavoidably long entry point)
        self._running = True
        state = self._state
        camera: Camera | None = None
        voice_listener: VoiceCommandListener | None = None
        face_security_manager: FaceSecurityManager | None = None

        try:
            config = Config()
            get_mmgi_logger()  # ensure logger is initialized once on worker start
            low_conf_threshold = float(config.get('hand_tracking.min_detection_confidence'))

            voice_cfg = _load_voice_control_settings(config)
            voice_listener = VoiceCommandListener(
                enabled=bool(voice_cfg.get('enabled', True)),
                listen_timeout_s=float(voice_cfg.get('listen_timeout_s', 1.2)),
                phrase_time_limit_s=float(voice_cfg.get('phrase_time_limit_s', 2.0)),
                energy_threshold=int(voice_cfg.get('energy_threshold', 250)),
                recognition_language=str(voice_cfg.get('recognition_language', 'en-IN')),
            )
            voice_enabled_for_fusion = voice_listener.is_enabled
            voice_system_mode_only = bool(voice_cfg.get('system_mode_only', True))
            voice_listener.start()
            state.set_voice_listener_enabled(voice_enabled_for_fusion)
            state.set_voice_command('Listening...' if voice_enabled_for_fusion else 'Voice Unavailable')
            last_voice_error: str | None = None

            camera = Camera(
                width  = config.get('camera.width'),
                height = config.get('camera.height'),
                fps    = config.get('camera.fps'),
            )
            camera_retry_attempts = int(config.get('lifecycle.camera_retry_attempts', 3) or 3)
            camera_retry_delay_s = float(config.get('lifecycle.camera_retry_delay_s', 1.0) or 1.0)
            camera_opened = False
            for attempt in range(1, camera_retry_attempts + 1):
                if camera.open():
                    camera_opened = True
                    break
                log_runtime_error(f'Camera open failed (attempt {attempt}/{camera_retry_attempts})')
                state.emit_log(_ts(), 'ERROR', f'Camera unavailable (attempt {attempt}/{camera_retry_attempts})')
                time.sleep(camera_retry_delay_s)

            if not camera_opened:
                log_lifecycle_event('camera_init', 'failed', 'All retry attempts exhausted')
                self.error.emit('Could not open camera.')
                return

            hand_tracker = HandTracker(
                max_num_hands            = config.get('hand_tracking.max_num_hands'),
                min_detection_confidence = config.get('hand_tracking.min_detection_confidence'),
                min_tracking_confidence  = config.get('hand_tracking.min_tracking_confidence'),
            )

            gesture_classifier = GestureClassifier()
            calibration = CalibrationManager()
            profile = calibration.profile
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
                open_palm_duration   = profile.gesture_hold_seconds,
                cooldown_duration    = config.get('activation.cooldown_duration'),
                stability_threshold  = profile.stability_frames,
            )

            decision_engine = DecisionEngine(
                stability_frames=profile.stability_frames,
                hold_seconds=profile.mode_switch_hold_seconds,
                cooldown_seconds=profile.mode_switch_cooldown_seconds,
            )
            mode_manager = ModeManager(cooldown_s=profile.mode_switch_cooldown_seconds, initial_mode=decision_engine.current_mode)
            face_security_cfg = _load_face_security_settings(config)
            face_security_manager = FaceSecurityManager(
                enabled=bool(face_security_cfg.get('enabled', True)),
                authorized_image_path=str(face_security_cfg.get('authorized_image_path', 'config/authorized_face.jpg')),
                authorized_encoding_path=str(face_security_cfg.get('authorized_encoding_path', 'config/authorized_face_encoding.json')),
                similarity_threshold=float(face_security_cfg.get('similarity_threshold', 0.84)),
                min_detection_confidence=float(face_security_cfg.get('min_detection_confidence', 0.6)),
                eval_interval_s=float(face_security_cfg.get('eval_interval_s', 0.08)),
                away_delay_s=float(face_security_cfg.get('away_delay_s', 2.5)),
                return_confirm_s=float(face_security_cfg.get('return_confirm_s', 0.7)),
            )
            state.set_face_security_enabled(bool(face_security_cfg.get('enabled', True)))
            state.set_gesture_control_enabled(True)
            state.request_mode(mode_manager.current_mode)

            action_executor = ActionExecutor(config={
                'brave_path':        config.get('apps.brave_path'),
                'apple_music_aumid': config.get('apps.apple_music_aumid'),
            })
            unified_pipeline = UnifiedDecisionPipeline(
                decision_engine=decision_engine,
                action_executor=action_executor,
                mode_manager=mode_manager,
                face_security=face_security_manager,
            )
            fusion_layer = MultimodalFusionLayer()

            fps_counter = FPSCounter()
            gesture_filter = GestureStabilityFilter(confirm_frames=profile.stability_frames, min_switch_interval_s=0.25)
            metrics = MetricsManager()
            last_logged_gesture: str | None = None
            last_no_hand_log = 0.0
            last_low_conf_log = 0.0
            last_invalid_log = 0.0
            uncertainty_streak = 0
            uncertainty_lock_until = 0.0
            last_uncertainty_log = 0.0
            last_face_auth_signature: tuple[bool, str] | None = None
            voice_backoff_until = 0.0

            warning_interval = 1.5
            error_interval = 1.5

            state.emit_log(_ts(), 'SYSTEM', 'Pipeline started — show Open Palm to activate')
            log_pipeline_state('Pipeline started')
            log_lifecycle_event('pipeline', 'started', 'Worker loop active')
            state.set_face_auth(True, 'Face Security: Login Only')
            state.set_activation_lock(True, 'Waiting for stable gesture')

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
                with self._frame_lock:
                    self._latest_frame_bgr = frame.copy()

                # ----------------------------------------------------------
                # Voice command polling (non-blocking)
                # ----------------------------------------------------------
                with self._settings_lock:
                    should_reload_calibration = self._reload_calibration_requested
                    self._reload_calibration_requested = False

                if should_reload_calibration:
                    profile = calibration.load()
                    activation_manager._open_palm_duration = profile.gesture_hold_seconds
                    activation_manager._stability_threshold = profile.stability_frames
                    decision_engine.set_runtime_timing(
                        stability_frames=profile.stability_frames,
                        hold_seconds=profile.mode_switch_hold_seconds,
                        cooldown_seconds=profile.mode_switch_cooldown_seconds,
                    )
                    mode_manager._cooldown_s = profile.mode_switch_cooldown_seconds
                    gesture_filter.set_confirm_frames(profile.stability_frames)
                    state.emit_log(_ts(), 'SYSTEM', 'Calibration reloaded from settings')

                if state.requested_mode != mode_manager.current_mode:
                    mode_manager.set_mode(state.requested_mode)
                    decision_engine.current_mode = mode_manager.current_mode
                    state.set_mode(mode_manager.current_mode)
                    state.emit_log(_ts(), 'MODE', f'Switched to {mode_manager.current_mode} (manual)')

                voice_enabled_for_fusion = bool(state.voice_listener_enabled) and voice_listener is not None and voice_listener.is_enabled
                gesture_processing_enabled = bool(state.gesture_control_enabled)
                face_security_enabled = bool(state.face_security_enabled)

                voice_event = None
                if voice_listener is not None and voice_enabled_for_fusion:
                    voice_event = voice_listener.poll_latest()
                    if voice_event is not None:
                        if time.time() < voice_backoff_until:
                            state.set_voice_command('Voice in recovery window...')
                            voice_event = None
                        else:
                            if voice_event.command == '__unmapped__':
                                transcript = voice_event.transcript.strip()
                                if len(transcript) > 48:
                                    transcript = transcript[:45] + '...'
                                state.set_voice_command(f'Heard: {transcript}')
                                log_voice_command_event(voice_event.transcript, mapped=False, details='unmapped')
                                state.emit_log(_ts(), 'SYSTEM', f'Voice heard (unmapped): {voice_event.transcript}')
                            else:
                                voice_text = _voice_label(voice_event.command)
                                state.set_voice_command(voice_text)
                                log_voice_command_event(voice_event.command, mapped=True, details='recognized')
                                state.emit_log(_ts(), 'ACTION', f'Voice command detected: {voice_text}')
                    elif voice_listener.last_error and voice_listener.last_error != last_voice_error:
                        last_voice_error = voice_listener.last_error
                        voice_backoff_until = time.time() + 5.0
                        state.set_voice_command(f'Voice Error: {last_voice_error}')
                        log_voice_command_event('voice_error', mapped=False, details=last_voice_error)
                        state.emit_log(_ts(), 'SYSTEM', f'Voice listener error: {last_voice_error}')
                    elif voice_listener.is_enabled and voice_listener.is_ready and state.voice_command == 'Listening...':
                        state.set_voice_command('Mic Active - Speak Command')
                elif not state.voice_listener_enabled:
                    state.set_voice_command('Voice Control Off')

                face_authorized = True
                face_status = face_security_manager.setup_status_text
                mode_is_system = mode_manager.current_mode == 'System Mode'
                if mode_is_system and face_security_enabled:
                    face_result = face_security_manager.evaluate(frame)
                    face_authorized = face_result.is_authorized
                    prefix = 'UNLOCKED' if face_result.is_authorized else 'LOCKED'
                    face_status = f'{prefix} | {face_result.status_text}'
                    signature = (face_result.is_authorized, face_result.status_text)
                    if signature != last_face_auth_signature:
                        last_face_auth_signature = signature
                        log_face_authorization_event(
                            face_result.is_authorized,
                            face_result.status_text,
                            face_result.similarity,
                        )
                elif mode_is_system and not face_security_enabled:
                    face_authorized = True
                    face_status = 'UNLOCKED | Face security disabled'
                state.set_face_auth(face_authorized, face_status)

                # ----------------------------------------------------------
                # Hand detection + gesture classification
                # ----------------------------------------------------------
                skip_hand_processing = not gesture_processing_enabled
                detection_result = None
                hands_info = {}
                if not skip_hand_processing:
                    detection_result = hand_tracker.detect_hands(frame)
                    hands_info = hand_tracker.get_hands_info(detection_result)

                gesture: str | None = None
                confidence          = 0.0
                ui_gesture_text = 'Gesture unclear'
                gesture_verification_status = 'Not Detected'
                custom_match = None
                custom_action: str | None = None

                # Prefer right hand; fall back to left
                hand_data = hands_info.get('right') or hands_info.get('left')
                if hand_data:
                    state.set_landmarks(hand_data.get('landmarks'))
                    hand_distance = calibration.estimate_hand_distance(hand_data.get('landmarks'))
                    dynamic_sensitivity = calibration.cursor_sensitivity_for_distance(hand_distance)
                    state.set_cursor_sensitivity(dynamic_sensitivity)
                    confidence = float(hand_data.get('confidence', 0.0))

                    if confidence < low_conf_threshold:
                        uncertainty_streak += 1
                        gesture, _ = gesture_filter.update(None, hand_present=True)
                        ui_gesture_text = 'Gesture unclear'
                        gesture_verification_status = 'Unstable'
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
                                uncertainty_streak += 1
                                gesture, _ = gesture_filter.update(None, hand_present=True)
                                ui_gesture_text = 'Gesture unclear'
                                gesture_verification_status = 'Unstable'
                                last_logged_gesture = None
                                now = time.time()
                                if now - last_invalid_log >= error_interval:
                                    log_runtime_error('Invalid gesture detected')
                                    last_invalid_log = now
                            else:
                                gesture, stable_state = gesture_filter.update(raw_gesture, hand_present=True)
                                metrics.record_gesture_event(confirmed=(stable_state == 'stable' and gesture is not None))
                                if stable_state == 'stable' and gesture is not None:
                                    uncertainty_streak = 0
                                    ui_gesture_text = gesture
                                    gesture_verification_status = 'Stable'
                                    if gesture != last_logged_gesture:
                                        log_gesture_detected(gesture)
                                        last_logged_gesture = gesture
                                else:
                                    uncertainty_streak += 1
                                    ui_gesture_text = 'Gesture unclear'
                                    gesture_verification_status = 'Unstable'
                                    last_logged_gesture = None
                        else:
                            # Keep the predefined gesture filter clean while custom is active.
                            gesture_filter.update(None, hand_present=True)
                            gesture_verification_status = 'Stable'

                    # Draw hand skeleton
                    if detection_result is not None:
                        hand_tracker.draw_landmarks(frame, detection_result)
                else:
                    if gesture_processing_enabled:
                        uncertainty_streak += 1
                        gesture, _ = gesture_filter.update(None, hand_present=False)
                        state.set_landmarks(None)
                        state.set_cursor_sensitivity(profile.base_cursor_sensitivity)
                        if custom_confirmation is not None:
                            custom_confirmation.reset()
                        ui_gesture_text = 'No hand detected'
                        gesture_verification_status = 'Not Detected'
                        now = time.time()
                        if now - last_no_hand_log >= error_interval:
                            log_runtime_error('No hand detected')
                            last_no_hand_log = now
                        last_logged_gesture = None
                    else:
                        gesture = None
                        ui_gesture_text = 'Gesture Control Off'
                        gesture_verification_status = 'Disabled'
                        state.set_landmarks(None)
                        state.set_cursor_sensitivity(profile.base_cursor_sensitivity)

                # ----------------------------------------------------------
                # Activation manager + unified event pipeline
                # ----------------------------------------------------------
                should_execute = activation_manager.update(gesture)
                state.set_system_active(activation_manager.is_active)
                state.set_cooldown(activation_manager.is_in_cooldown)

                pending_events = []
                gesture_event = None
                voice_input_event = None

                if uncertainty_streak >= 8:
                    uncertainty_lock_until = max(uncertainty_lock_until, time.time() + 0.8)
                    uncertainty_streak = 0

                if time.time() < uncertainty_lock_until:
                    if time.time() - last_uncertainty_log > 1.0:
                        last_uncertainty_log = time.time()
                        state.emit_log(_ts(), 'SYSTEM', 'Safety lock: actions paused due to uncertain input')
                        log_runtime_error('Safety lock active due to uncertain gesture input')
                else:
                    if custom_action and should_execute:
                        # Custom gestures bypass map lookup but still use unified execution path.
                        custom_event = InputEventNormalizer.from_gesture(
                            gesture='Custom Action',
                            confidence=confidence,
                        )
                        pending_events.append((custom_event, custom_action, 'Custom Gesture'))
                    elif gesture:
                        if decision_engine.is_mode_switch(gesture) or should_execute:
                            gesture_event = InputEventNormalizer.from_gesture(
                                gesture=gesture,
                                confidence=confidence,
                            )

                    if voice_event is not None and voice_event.command != '__unmapped__' and voice_enabled_for_fusion:
                        if (not voice_system_mode_only) or mode_manager.current_mode == 'System Mode':
                            voice_command = voice_event.command
                            voice_input_event = InputEventNormalizer.from_voice(
                                command=voice_command,
                                confidence=1.0,
                                timestamp=voice_event.timestamp,
                            )

                    fused_events = fusion_layer.merge(
                        gesture_event=gesture_event,
                        voice_event=voice_input_event,
                        gesture_is_stable=bool(gesture_event is not None),
                        uncertainty_lock_active=time.time() < uncertainty_lock_until,
                    )
                    for fused_event in fused_events:
                        label = 'Voice' if fused_event.type == 'voice' else mode_manager.current_mode
                        pending_events.append((fused_event, None, label))

                for event, forced_action, source_label in pending_events:
                    if forced_action is not None:
                        if mode_manager.current_mode == 'System Mode':
                            auth = face_security_manager.evaluate(frame) if (face_security_manager is not None and face_security_enabled) else None
                            if auth is not None and not auth.is_authorized:
                                metrics.record_activation_attempt(succeeded=False)
                                state.emit_log(_ts(), 'SECURITY', f'Blocked action in System Mode: {auth.status_text}')
                                continue
                        action_executor.execute(forced_action)
                        metrics.record_activation_attempt(succeeded=True)
                        label = action_executor._LABELS.get(forced_action, forced_action)
                        state.emit_log(_ts(), 'ACTION', f'{label}  [{source_label}]')
                        state.set_action_executed(forced_action)
                        log_action_executed(label)
                        continue

                    result = unified_pipeline.process_event(
                        event,
                        frame_bgr=frame,
                        enforce_face_security=face_security_enabled,
                    )

                    if result.mode_changed:
                        metrics.record_mode_switch()
                        state.set_mode(result.mode)
                        # Keep manual mode request in sync with pipeline-driven switches.
                        if state.requested_mode != result.mode:
                            state.request_mode(result.mode)
                        state.emit_log(_ts(), 'MODE', f'Switched to {result.mode}')

                    if result.blocked_reason == 'face_unauthorized':
                        metrics.record_activation_attempt(succeeded=False)
                        state.emit_log(_ts(), 'SECURITY', f'Blocked action in System Mode: {result.security_status}')

                    if result.action:
                        metrics.record_activation_attempt(succeeded=True)
                        label = action_executor._LABELS.get(result.action, result.action)
                        state.emit_log(_ts(), 'ACTION', f'{label}  [{source_label}]')
                        state.set_action_executed(result.action)
                        log_action_executed(label)

                decision_engine.current_mode = mode_manager.current_mode
                state.set_mode_stability(decision_engine.mode_stability_progress)
                state.set_gesture_status(gesture_verification_status)

                lock_reason = 'Ready'
                activation_locked = False
                if not gesture_processing_enabled:
                    activation_locked = True
                    lock_reason = 'Gesture control disabled'
                elif time.time() < uncertainty_lock_until:
                    activation_locked = True
                    lock_reason = 'Uncertain gesture input'
                elif mode_manager.current_mode == 'System Mode' and face_security_enabled and not face_authorized:
                    activation_locked = True
                    lock_reason = 'Face not authorized'
                elif gesture_verification_status != 'Stable':
                    activation_locked = True
                    lock_reason = 'Waiting for stable gesture'
                state.set_activation_lock(activation_locked, lock_reason)

                # ----------------------------------------------------------
                # Update telemetry
                # ----------------------------------------------------------
                fps_counter.update()
                latency_ms = (time.perf_counter() - t_start) * 1000

                state.set_gesture(ui_gesture_text)
                state.set_confidence(confidence)
                state.set_fps(fps_counter.fps)
                state.set_latency(latency_ms)
                metrics.record_latency(latency_ms)
                snap = metrics.flush_report()
                state.set_metrics({
                    'gesture_accuracy_pct': snap.gesture_accuracy_pct,
                    'false_activation_rate_pct': snap.false_activation_rate_pct,
                    'avg_response_latency_ms': snap.avg_response_latency_ms,
                    'mode_switches_per_min': snap.mode_switches_per_min,
                })

                # ----------------------------------------------------------
                # Annotate and emit frame
                # ----------------------------------------------------------
                debug_text = None
                if profile.debug_overlay_enabled:
                    debug_text = (
                        f'Debug | Sens:{state.cursor_sensitivity:.2f} '
                        f'Acc:{snap.gesture_accuracy_pct:.1f}% '
                        f'FalseAct:{snap.false_activation_rate_pct:.1f}% '
                        f'AvgLat:{snap.avg_response_latency_ms:.1f}ms'
                    )

                _draw_overlay(
                    frame,
                    gesture,
                    mode_manager.current_mode,
                    activation_manager.is_active,
                    fps_counter.fps,
                    face_status=face_status if mode_manager.current_mode == 'System Mode' else None,
                    face_authorized=face_authorized if mode_manager.current_mode == 'System Mode' else None,
                    debug_text=debug_text,
                )

                self.frame_ready.emit(_frame_to_qimage(frame))

            # ---- Loop exited cleanly ---
            camera.release()
            hand_tracker.close()
            if voice_listener is not None:
                voice_listener.stop()
            if face_security_manager is not None:
                face_security_manager.close()
            metrics.flush_report(force=True)
            state.set_system_active(False)
            state.emit_log(_ts(), 'SYSTEM', 'Pipeline stopped')
            log_pipeline_state('Pipeline stopped')
            log_lifecycle_event('pipeline', 'stopped', 'Worker loop exited cleanly')

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
                if voice_listener is not None:
                    voice_listener.stop()
            except Exception:
                pass
            try:
                if face_security_manager is not None:
                    face_security_manager.close()
            except Exception:
                pass
            log_lifecycle_event('pipeline', 'error', str(exc))
