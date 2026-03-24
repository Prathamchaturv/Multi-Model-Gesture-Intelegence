"""Headless CLI runner for MMGI.

Runs the full gesture pipeline without the PyQt UI:
Camera -> Hand Tracking -> Gesture Classification -> Decision Pipeline -> Action Executor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

# Allow running this file directly with: python cli/main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.camera import Camera
from core.face_security import FaceSecurityManager
from core.gesture_classifier import GestureClassifier
from core.hand_tracking import HandTracker
from engine.action_executor import ActionExecutor
from engine.activation_manager import ActivationManager
from engine.decision_engine import DecisionEngine
from engine.unified_pipeline import InputEventNormalizer, ModeManager, UnifiedDecisionPipeline
from utils.config import Config

_MODE_MAP = {
    'app': 'App Mode',
    'media': 'Media Mode',
    'system': 'System Mode',
}


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the headless runner."""
    parser = argparse.ArgumentParser(
        description='MMGI headless CLI mode (no GUI)',
    )
    parser.add_argument(
        '--mode',
        choices=sorted(_MODE_MAP.keys()),
        default='app',
        help='Initial mode to start in: app, media, or system.',
    )
    parser.add_argument(
        '--max-frames',
        type=int,
        default=0,
        help='Exit after N frames. Use 0 to run indefinitely.',
    )
    return parser.parse_args()


def build_runtime(initial_mode: str) -> dict[str, object]:
    """Create all reusable pipeline components for CLI execution."""
    config = Config()

    camera = Camera(
        width=config.get('camera.width'),
        height=config.get('camera.height'),
        fps=config.get('camera.fps'),
    )
    hand_tracker = HandTracker(
        max_num_hands=config.get('hand_tracking.max_num_hands'),
        min_detection_confidence=config.get('hand_tracking.min_detection_confidence'),
        min_tracking_confidence=config.get('hand_tracking.min_tracking_confidence'),
    )
    gesture_classifier = GestureClassifier()

    activation_manager = ActivationManager(
        open_palm_duration=config.get('activation.open_palm_duration'),
        cooldown_duration=config.get('activation.cooldown_duration'),
        stability_threshold=config.get('activation.stability_threshold'),
    )

    decision_engine = DecisionEngine()
    decision_engine.current_mode = initial_mode
    mode_manager = ModeManager(initial_mode=initial_mode)

    face_security = FaceSecurityManager(
        enabled=bool(config.get('face_security.enabled', True)),
        authorized_image_path=str(config.get('face_security.authorized_image_path', 'config/authorized_face.jpg')),
        authorized_encoding_path=str(config.get('face_security.authorized_encoding_path', 'config/authorized_face_encoding.json')),
        similarity_threshold=float(config.get('face_security.similarity_threshold', 0.84)),
        min_detection_confidence=float(config.get('face_security.min_detection_confidence', 0.6)),
        eval_interval_s=float(config.get('face_security.eval_interval_s', 0.08)),
        away_delay_s=float(config.get('face_security.away_delay_s', 2.5)),
        return_confirm_s=float(config.get('face_security.return_confirm_s', 0.7)),
    )

    action_executor = ActionExecutor(
        config={
            'brave_path': config.get('apps.brave_path'),
            'apple_music_aumid': config.get('apps.apple_music_aumid'),
        }
    )

    unified_pipeline = UnifiedDecisionPipeline(
        decision_engine=decision_engine,
        action_executor=action_executor,
        mode_manager=mode_manager,
        face_security=face_security,
    )

    return {
        'camera': camera,
        'hand_tracker': hand_tracker,
        'gesture_classifier': gesture_classifier,
        'activation_manager': activation_manager,
        'decision_engine': decision_engine,
        'unified_pipeline': unified_pipeline,
    }


def run_cli(mode: str, max_frames: int) -> int:
    """Run the headless frame loop until interrupted or max frame count is reached."""
    initial_mode = _MODE_MAP[mode]
    runtime = build_runtime(initial_mode)

    camera: Camera = runtime['camera']  # type: ignore[assignment]
    hand_tracker: HandTracker = runtime['hand_tracker']  # type: ignore[assignment]
    gesture_classifier: GestureClassifier = runtime['gesture_classifier']  # type: ignore[assignment]
    activation_manager: ActivationManager = runtime['activation_manager']  # type: ignore[assignment]
    decision_engine: DecisionEngine = runtime['decision_engine']  # type: ignore[assignment]
    unified_pipeline: UnifiedDecisionPipeline = runtime['unified_pipeline']  # type: ignore[assignment]

    if max_frames < 0:
        print('[CLI] --max-frames must be >= 0')
        return 2

    if not camera.open():
        print('[CLI] Could not open camera. Exiting.')
        return 1

    print('=' * 64)
    print('MMGI Headless CLI Mode')
    print(f'Initial mode: {initial_mode}')
    print('Activation: hold Open Palm, deactivate with Fist, Ctrl+C to stop')
    if max_frames > 0:
        print(f'Auto-exit after frames: {max_frames}')
    else:
        print('Auto-exit after frames: disabled')
    print('=' * 64)

    processed_frames = 0

    try:
        while True:
            ok, frame = camera.read_frame()
            if not ok or frame is None:
                print('[CLI] Camera frame read failed. Ending loop.')
                break

            # Mirror frame to match expected hand orientation from UI mode.
            frame = cv2.flip(frame, 1)

            # Run hand tracking and extract the most relevant hand payload.
            results = hand_tracker.detect_hands(frame)
            hands_info = hand_tracker.get_hands_info(results)
            hand_data = hands_info.get('right') or hands_info.get('left')

            gesture: str | None = None
            if hand_data:
                gesture = gesture_classifier.classify(hand_data['finger_states'])
                if gesture == 'Unknown':
                    gesture = None

            # Reuse existing activation gate so actions only fire when intentionally enabled.
            should_execute_action = activation_manager.update(gesture)

            if gesture and (decision_engine.is_mode_switch(gesture) or should_execute_action):
                event = InputEventNormalizer.from_gesture(gesture=gesture, confidence=1.0)
                decision = unified_pipeline.process_event(event, frame_bgr=frame)

                if decision.mode_changed:
                    print(f'[CLI] Mode changed -> {decision.mode}')
                elif decision.blocked_reason:
                    print(f'[CLI] Action blocked: {decision.blocked_reason}')
                elif decision.action:
                    print(f'[CLI] Action executed: {decision.action}')

            processed_frames += 1
            if max_frames and processed_frames >= max_frames:
                print(f'[CLI] Reached max frames ({max_frames}). Exiting.')
                break

    except KeyboardInterrupt:
        print('\n[CLI] Keyboard interrupt received. Shutting down cleanly...')
    finally:
        camera.release()
        hand_tracker.close()
        cv2.destroyAllWindows()
        print('[CLI] Cleanup complete.')

    return 0


def main() -> int:
    args = parse_args()
    return run_cli(mode=args.mode, max_frames=args.max_frames)


if __name__ == '__main__':
    raise SystemExit(main())
