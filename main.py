"""
Module: main.py
Description: Entry-point dispatcher for MMGI — launches the PyQt6 dashboard
             (default) or the headless OpenCV pipeline (--headless flag).
Author: Pratham Chaturvedi

MMGI - Multi-Modal Gesture Intelligence

Entry-point dispatcher
──────────────────────
Default (no flags)  → PyQt6 AI Dashboard  (live camera + Smart Mode UI)
--headless          → OpenCV terminal-only pipeline (original behaviour)

Usage
-----
  python main.py                  # launch dashboard
  python main.py --headless       # headless OpenCV loop
    python main.py --no-ui          # headless CLI mode (preferred)
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------------
# Headless (OpenCV) pipeline  –  preserved from original main.py
# ---------------------------------------------------------------------------

def run_headless(max_frames: int = 0) -> None:
    """Original OpenCV gesture pipeline (no GUI)."""
    import cv2
    from core.adaptive_gesture_learning import (
        AdaptiveGestureMatcher,
        CustomGestureStore,
        MultiFrameGestureConfirmation,
    )
    from core.camera              import Camera
    from core.hand_tracking       import HandTracker
    from core.gesture_engine      import GestureClassifier
    from core.face_security       import FaceSecurityManager
    from engine.activation_manager import ActivationManager
    from core.decision_engine      import DecisionEngine
    from engine.context_aware_gesture import get_context, handle_gesture
    from execution.cursor_control  import ActionExecutor
    from engine.unified_pipeline   import InputEventNormalizer, ModeManager, UnifiedDecisionPipeline
    from utils.fps_counter         import FPSCounter
    from utils.config              import Config

    print('=' * 60)
    print('MMGI  —  Headless OpenCV Mode')
    print('=' * 60)

    config = Config()
    camera = camera_obj = None
    hand_tracker = None

    try:
        camera_obj = Camera(
            width  = config.get('camera.width'),
            height = config.get('camera.height'),
            fps    = config.get('camera.fps'),
        )
        if not camera_obj.open():
            print('  ✗ Failed to open camera'); return

        hand_tracker       = HandTracker(
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
        decision_engine    = DecisionEngine()
        mode_manager       = ModeManager(initial_mode=decision_engine.current_mode)
        face_security      = FaceSecurityManager(
            enabled=bool(config.get('face_security.enabled', True)),
            authorized_image_path=str(config.get('face_security.authorized_image_path', 'config/authorized_face.jpg')),
            authorized_encoding_path=str(config.get('face_security.authorized_encoding_path', 'config/authorized_face_encoding.json')),
            similarity_threshold=float(config.get('face_security.similarity_threshold', 0.84)),
            min_detection_confidence=float(config.get('face_security.min_detection_confidence', 0.6)),
            eval_interval_s=float(config.get('face_security.eval_interval_s', 0.08)),
            away_delay_s=float(config.get('face_security.away_delay_s', 2.5)),
            return_confirm_s=float(config.get('face_security.return_confirm_s', 0.7)),
        )
        custom_matcher = None
        custom_confirm = None
        if bool(config.get('adaptive_gesture.enabled', True)):
            custom_store_path = str(config.get('adaptive_gesture.store_path') or 'config/custom_gestures.json')
            custom_store_file = Path(custom_store_path)
            if not custom_store_file.is_absolute():
                custom_store_file = Path(__file__).parent / custom_store_file
            custom_store = CustomGestureStore(custom_store_file)
            custom_matcher = AdaptiveGestureMatcher(
                store=custom_store,
                threshold=float(config.get('adaptive_gesture.match_threshold') or 0.12),
            )
            custom_confirm = MultiFrameGestureConfirmation(
                confirm_frames=int(config.get('adaptive_gesture.confirm_frames') or 4)
            )

        action_executor    = ActionExecutor(config={
            'brave_path':        config.get('apps.brave_path'),
            'apple_music_aumid': config.get('apps.apple_music_aumid'),
        })
        unified_pipeline = UnifiedDecisionPipeline(
            decision_engine=decision_engine,
            action_executor=action_executor,
            mode_manager=mode_manager,
            face_security=face_security,
        )
        fps_counter        = FPSCounter()

        print('[Ready] Show Open Palm 2 s to activate. Keyboard: s=start/resume, p=pause, q/ESC=quit.\n')

        win = 'MMGI Headless'
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 1280, 720)
        processing_enabled = True
        processed_frames = 0

        while True:
            ok, frame = camera_obj.read_frame()
            if not ok or frame is None:
                break
            frame = cv2.flip(frame, 1)
            fps_counter.update()

            results = None
            hands_info = {}
            if processing_enabled:
                results = hand_tracker.detect_hands(frame)
                hands_info = hand_tracker.get_hands_info(results)

            if results is not None and results.hand_landmarks:
                hand_tracker.draw_landmarks(frame, results)

            hand_data = hands_info.get('right') or hands_info.get('left')
            gesture   = None
            custom_action = None
            if processing_enabled and hand_data:
                if custom_matcher is not None and custom_confirm is not None:
                    custom_match = custom_matcher.match(hand_data.get('landmarks'))
                    stable_name = custom_confirm.update(
                        custom_match.name if custom_match is not None else None
                    )
                    if stable_name and custom_match is not None and custom_match.name == stable_name:
                        gesture = f'Custom: {custom_match.name}'
                        custom_action = custom_match.action

                if custom_action is None:
                    gesture = gesture_classifier.classify(hand_data['finger_states'])
                    if gesture == 'Unknown':
                        gesture = None
            elif processing_enabled and custom_confirm is not None:
                custom_confirm.reset()

            should_exec = activation_manager.update(gesture) if processing_enabled else False

            action = None
            if processing_enabled and custom_action and should_exec:
                action_executor.execute(custom_action)
                action = custom_action
            elif processing_enabled and gesture:
                if should_exec and not decision_engine.is_mode_switch(gesture):
                    context = get_context()
                    context_action = handle_gesture(gesture, context)
                    if context_action:
                        action_executor.execute(context_action)
                        action = context_action

                if decision_engine.is_mode_switch(gesture) or should_exec:
                    # Fall back to the existing mode-aware pipeline when there is
                    # no context override for the current gesture.
                    if action is None:
                        event = InputEventNormalizer.from_gesture(
                            gesture=gesture,
                            confidence=1.0,
                        )
                        decision = unified_pipeline.process_event(event, frame_bgr=frame)
                        if decision.mode_changed:
                            print(f'  Mode -> {decision.mode}')
                        action = decision.action

            if action:
                print(f'  Action: {action}')

            if processing_enabled:
                processed_frames += 1
                if max_frames > 0 and processed_frames >= max_frames:
                    print(f'\n[CLI] Reached max frames ({max_frames}). Exiting.')
                    break

            fps_counter.display_fps(frame)
            activation_manager.display_status(frame)
            if not processing_enabled:
                cv2.putText(
                    frame,
                    'PAUSED (press s to resume)',
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 200, 255),
                    2,
                    cv2.LINE_AA,
                )
            cv2.imshow(win, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            if key == ord('p') and processing_enabled:
                processing_enabled = False
                print('  [CLI] Processing paused')
            elif key == ord('s') and not processing_enabled:
                processing_enabled = True
                print('  [CLI] Processing resumed')

    except KeyboardInterrupt:
        pass
    finally:
        if camera_obj:
            camera_obj.release()
        if hand_tracker:
            hand_tracker.close()
        cv2.destroyAllWindows()
        print('\nMMGI Headless session ended.')


# ---------------------------------------------------------------------------
# Dashboard (PyQt6) launch
# ---------------------------------------------------------------------------

def run_dashboard() -> None:
    """Launch the PyQt6 Smart Mode AI dashboard, optionally gated by login."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore    import Qt
    from ui.main_window  import MainWindow
    from ui.login_window import LoginWindow
    from ui.auth_state   import auth_state

    app = QApplication(sys.argv)
    app.setApplicationName('MMGI')
    app.setApplicationDisplayName('MMGI — Smart Mode AI Controller')
    auth_state.reset()

    # Show login screen when enabled in config/users.json
    if LoginWindow.should_show():
        login = LoginWindow()
        if login.exec() != LoginWindow.DialogCode.Accepted:
            sys.exit(0)
    else:
        auth_state.set_authenticated('local-user')

    if not auth_state.is_authenticated:
        sys.exit(0)

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    auth_state.reset()
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line flags for dashboard vs no-UI execution."""
    parser = argparse.ArgumentParser(description='MMGI launcher')
    parser.add_argument(
        '--no-ui',
        action='store_true',
        help='Run headless mode without PyQt dashboard.',
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Backward-compatible alias for --no-ui.',
    )
    parser.add_argument(
        '--max-frames',
        type=int,
        default=0,
        help='Exit headless mode after N processed frames (0 = run until quit).',
    )
    return parser.parse_args(argv)

if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    if args.no_ui or args.headless:
        run_headless(max_frames=max(0, int(args.max_frames)))
    else:
        run_dashboard()
