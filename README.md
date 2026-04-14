# MMGI - Multi-Modal Gesture Intelligence

MMGI is a real-time desktop interaction system that combines computer vision, voice input, and safety gating to execute system actions reliably.

This README is structured for final-year project evaluation and emphasizes architecture quality, engineering rigor, and verifiable implementation evidence.

## 1. System Architecture (Modular Design)

MMGI follows a modular, layered architecture with clear separation of responsibilities.

### Architecture Overview

Input Layer
- Webcam frames
- Optional microphone commands

Perception Layer
- Hand detection and landmarks
- Gesture classification
- Face authorization signals

Decision and Policy Layer
- Mode-aware decision mapping
- Runtime safety policy and cooldown
- Adaptive authorization policy

Execution Layer
- System action dispatch (OS actions)
- Scroll and click controls

Presentation Layer
- PyQt6 dashboard and state visualization
- Optional headless execution mode

### Module Breakdown

- core: sensing and decision facades
  - gesture_engine
  - voice_engine
  - decision_engine
  - authorization_engine
- execution: action dispatch surfaces
  - cursor_control
  - scroll_control
- ui: dashboard and runtime worker
  - main_window
  - worker_thread
  - shared_state
- engine: orchestration components
  - unified_pipeline
  - activation_manager
  - runtime_controller
- utils: config and logger infrastructure

Reference files:
- [core/gesture_engine.py](core/gesture_engine.py)
- [core/voice_engine.py](core/voice_engine.py)
- [core/decision_engine.py](core/decision_engine.py)
- [core/authorization_engine.py](core/authorization_engine.py)
- [execution/cursor_control.py](execution/cursor_control.py)
- [execution/scroll_control.py](execution/scroll_control.py)
- [engine/unified_pipeline.py](engine/unified_pipeline.py)
- [ui/worker_thread.py](ui/worker_thread.py)

## 2. Data Flow (Camera -> Gesture -> Decision -> Action)

Primary runtime path:

1. Camera frame capture
2. Hand landmark detection
3. Gesture classification
4. Event normalization
5. Mode-aware decision resolution
6. Authorization and runtime checks
7. Action execution
8. UI and log updates

Concrete integration points:
- Frame processing and event loop: [ui/worker_thread.py](ui/worker_thread.py)
- Decision resolution and mode logic: [engine/decision_engine.py](engine/decision_engine.py)
- End-to-end orchestration: [engine/unified_pipeline.py](engine/unified_pipeline.py)
- Action dispatch: [engine/action_executor.py](engine/action_executor.py)

## 3. Engineering Practices

### 3.1 Latency Control

Implemented controls:
- Rolling FPS and per-frame latency measurement
- Runtime latency overload guard (targeted under 100 ms behavior)
- Adaptive processing scale and inference pacing

Evidence:
- FPS and latency update: [ui/worker_thread.py](ui/worker_thread.py#L1465)
- Overload protection and recovery: [ui/worker_thread.py](ui/worker_thread.py#L1289)
- Overlay telemetry rendering: [ui/worker_thread.py](ui/worker_thread.py#L303)

### 3.2 Backpressure Handling

Implemented controls:
- Bounded frame queue
- Queue overflow drop policy
- Stale-frame dropping (latest frame preference under load)

Evidence:
- Bounded queue setup and stale-drop logic: [ui/worker_thread.py](ui/worker_thread.py)
- Frame drop logging: [utils/logger.py](utils/logger.py#L219)

### 3.3 Failure Handling

Implemented controls:
- No hand detected -> suppress action
- Low confidence -> suppress action
- Camera and model recovery loops
- Runtime state transitions: RUNNING, PAUSED, ERROR

Evidence:
- Safety gate helper and runtime lock reasons: [ui/worker_thread.py](ui/worker_thread.py)
- Runtime state policy: [engine/runtime_controller.py](engine/runtime_controller.py)
- Error and warning logging: [utils/logger.py](utils/logger.py)

## 4. Feature List (With Proof)

1. Real-time gesture recognition
- Proof: [core/hand_tracking.py](core/hand_tracking.py), [core/gesture_classifier.py](core/gesture_classifier.py)

2. Voice command input and normalization
- Proof: [core/voice_control.py](core/voice_control.py), [core/voice_engine.py](core/voice_engine.py)

2b. Advanced voice command mapper with phrase variations and confidence scoring
- Configurable command groups with multi-phrase aliases (e.g., "go down", "scroll down" → `scroll_down`)
- Token-subset scoring for flexible phrase matching
- Hot-reload from `voice_control.json` without restart
- Confidence-based filtering to suppress low-likelihood commands
- Proof: [core/voice_control.py](core/voice_control.py#L34) (`VoiceCommandMapper`), [docs/VOICE_COMMAND_MAPPER.md](docs/VOICE_COMMAND_MAPPER.md), [tests/test_voice_command_mapper.py](tests/test_voice_command_mapper.py) (20 tests)

3. Multi-mode operation (App, Media, System)
- Proof: [engine/decision_engine.py](engine/decision_engine.py), [tests/test_mode_switching.py](tests/test_mode_switching.py)

4. Face authorization gating
- Proof: [core/face_security.py](core/face_security.py), [tests/test_unified_pipeline.py](tests/test_unified_pipeline.py)

5. Unified multimodal pipeline
- Proof: [engine/unified_pipeline.py](engine/unified_pipeline.py), [tests/test_integration_gesture_control_flow.py](tests/test_integration_gesture_control_flow.py)

6. Runtime telemetry overlay (FPS, latency, confidence)
- Proof: [ui/worker_thread.py](ui/worker_thread.py#L303)

7. Headless operation for no-UI execution
- Proof: [main.py](main.py#L266), [cli/main.py](cli/main.py)

8. Dynamic runtime tuning from configuration
- Proof: [config/settings.json](config/settings.json), [utils/settings_loader.py](utils/settings_loader.py)

## 5. Screenshots and Demo Explanation

Current repository assets include placeholders for report/demo media.

Available asset placeholders:
- [assets/ui_screenshot.png.placeholder.txt](assets/ui_screenshot.png.placeholder.txt)
- [assets/demo.gif.placeholder.txt](assets/demo.gif.placeholder.txt)
- [assets/workflow.png.placeholder.txt](assets/workflow.png.placeholder.txt)
- [assets/architecture.png.placeholder.txt](assets/architecture.png.placeholder.txt)

Suggested demo flow for evaluation:
1. Start GUI mode and show live dashboard updates.
2. Demonstrate activation gesture and one action in each mode.
3. Demonstrate voice command mapping.
4. Show safety behavior for low-confidence and no-hand conditions.
5. Run no-UI mode and show terminal logs.

## 6. How To Run

### Prerequisites

- Python 3.10+
- Windows 10/11 recommended
- Webcam
- Microphone for voice features

### Installation

1. Clone repository
2. Create virtual environment
3. Install dependencies from requirements.txt
4. Ensure hand_landmarker.task is present in project root

Example commands:
- python -m venv venv
- venv\Scripts\activate
- pip install -r requirements.txt

### Run GUI Mode

- python main.py

### First-Time Quick Guide (New User Flow)

1. Launch dashboard: `python main.py`
2. Click `Start` in the header.
3. Ensure your camera feed is visible and your face is in frame (if Face Security is enabled).
4. Show `Open Palm` for about 2 seconds to activate control.
5. Use one gesture at a time with a steady hand.
6. Switch mode by showing `Three Fingers` for ~1 second:
  - App Mode -> Media Mode -> System Mode -> App Mode
7. Check the right panel + runtime chips for safety state:
  - `LOCKED` / `User Away` means actions are paused until face auth recovers.
8. Open the in-app `Guide` tab (left sidebar) for step-by-step usage and live gesture mapping.

### Run Headless Mode (No UI)

- python main.py --no-ui

Backward-compatible alias:
- python main.py --headless

Optional frame limit:
- python main.py --no-ui --max-frames 600

### Run Dedicated CLI Runner

- python cli/main.py
- python cli/main.py --mode media --max-frames 600

Keyboard controls in no-UI OpenCV loop:
- s = start/resume processing
- p = pause processing
- q or ESC = stop and exit

## 7. Tech Stack

Core CV and AI:
- OpenCV
- MediaPipe
- NumPy

UI and runtime:
- PyQt6

Automation and system actions:
- PyAutoGUI

Voice:
- SpeechRecognition
- sounddevice

Security:
- bcrypt

Testing:
- pytest

Dependency source:
- [requirements.txt](requirements.txt)

## 8. Test and Verification

Run full tests:
- python -m pytest -q

Integration-oriented references:
- [tests/test_unified_pipeline.py](tests/test_unified_pipeline.py)
- [tests/test_pipeline_lifecycle.py](tests/test_pipeline_lifecycle.py)
- [tests/test_integration_gesture_control_flow.py](tests/test_integration_gesture_control_flow.py)
- [tests/TEST_SUITE_GUIDE.md](tests/TEST_SUITE_GUIDE.md)

## 9. Configuration and Tuning

Core runtime tuning keys are in settings.json:
- gesture_threshold
- voice_confidence
- cooldown
- cursor_sensitivity

References:
- [config/settings.json](config/settings.json)
- [utils/settings_loader.py](utils/settings_loader.py)

## 10. Evaluator Notes

Engineering strengths:
- Modular architecture with explicit responsibility boundaries
- Observable runtime with telemetry and structured logging
- Safety-first decision gating under uncertain inputs
- Backpressure and latency protections in real-time loop
- Reproducible tests across critical control paths

Potential future enhancements:
- Cross-platform action adapters beyond Windows-centric automation
- Expanded benchmark suite with hardware profile baselines
- Persistent experiment reports for tuning comparisons
