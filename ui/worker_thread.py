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

import time
from datetime import datetime

import cv2
from PyQt6.QtCore  import QThread, pyqtSignal
from PyQt6.QtGui   import QImage

from core.camera                 import Camera
from core.hand_tracking          import HandTracker
from core.gesture_classifier     import GestureClassifier
from core.system_mode_engine     import AirMouseController
from engine.activation_manager   import ActivationManager
from engine.decision_engine      import DecisionEngine
from engine.action_executor      import ActionExecutor
from utils.fps_counter           import FPSCounter
from utils.config                import Config
from utils.logger                import get_mmgi_logger
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

def _ts() -> str:
    return datetime.now().strftime('%H:%M:%S')


def _draw_overlay(frame, gesture: str | None, mode: str,
                  is_active: bool, fps: float) -> None:
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

        try:
            config = Config()
            runtime_logger = get_mmgi_logger()
            low_conf_threshold = float(config.get('hand_tracking.min_detection_confidence'))

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
            last_logged_gesture: str | None = None
            last_no_hand_log = 0.0
            last_low_conf_log = 0.0
            last_invalid_log = 0.0

            warning_interval = 1.5
            error_interval = 1.5

            state.emit_log(_ts(), 'SYSTEM', 'Pipeline started — show Open Palm to activate')
            runtime_logger.info('Pipeline started')

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
                # Hand detection + gesture classification
                # ----------------------------------------------------------
                detection_result = hand_tracker.detect_hands(frame)
                hands_info       = hand_tracker.get_hands_info(detection_result)

                gesture: str | None = None
                confidence          = 0.0

                # Prefer right hand; fall back to left
                hand_data = hands_info.get('right') or hands_info.get('left')
                if hand_data:
                    confidence = float(hand_data.get('confidence', 0.0))

                    if confidence < low_conf_threshold:
                        now = time.time()
                        if now - last_low_conf_log >= warning_interval:
                            runtime_logger.warning('Low confidence gesture (confidence=%.2f)', confidence)
                            last_low_conf_log = now
                    else:
                        finger_states = hand_data['finger_states']
                        gesture = gesture_classifier.classify(finger_states)
                        if gesture == 'Unknown':
                            now = time.time()
                            if now - last_invalid_log >= error_interval:
                                runtime_logger.error('Invalid gesture detected')
                                last_invalid_log = now
                            gesture = None
                        elif gesture != last_logged_gesture:
                            runtime_logger.info('Gesture detected: %s', gesture)
                            last_logged_gesture = gesture

                    # Draw hand skeleton
                    hand_tracker.draw_landmarks(frame, detection_result)
                else:
                    now = time.time()
                    if now - last_no_hand_log >= error_interval:
                        runtime_logger.error('No hand detected')
                        last_no_hand_log = now
                    last_logged_gesture = None

                # ----------------------------------------------------------
                # Smart Mode decision
                # ----------------------------------------------------------
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
                should_execute = activation_manager.update(gesture)
                state.set_system_active(activation_manager.is_active)
                state.set_cooldown(activation_manager.is_in_cooldown)

                # ----------------------------------------------------------
                # Execute action  (System Mode → air mouse; others → executor)
                # ----------------------------------------------------------
                if decision_engine.current_mode == 'System Mode' and activation_manager.is_active:
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
                            runtime_logger.info('Action executed: %s', am_label)
                elif should_execute and action:
                    action_executor.execute(action)
                    label = action_executor._LABELS.get(action, action)
                    state.emit_log(_ts(), 'ACTION', f'{label}  [{decision_engine.current_mode}]')
                    state.set_action_executed(action)
                    runtime_logger.info('Action executed: %s', label)

                # ----------------------------------------------------------
                # Update telemetry
                # ----------------------------------------------------------
                fps_counter.update()
                latency_ms = (time.perf_counter() - t_start) * 1000

                state.set_gesture(gesture or '')
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
                )

                self.frame_ready.emit(_frame_to_qimage(frame))

            # ---- Loop exited cleanly ---
            camera.release()
            hand_tracker.close()
            state.set_system_active(False)
            state.emit_log(_ts(), 'SYSTEM', 'Pipeline stopped')
            runtime_logger.info('Pipeline stopped')

        except Exception as exc:
            import traceback
            msg = f'Pipeline error: {exc}\n{traceback.format_exc()}'
            self.error.emit(msg)
            try:
                get_mmgi_logger().error('Pipeline error: %s', exc)
            except Exception:
                pass
            try:
                if camera is not None:
                    camera.release()
            except Exception:
                pass
