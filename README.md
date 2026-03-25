# MMGI (Multi-Modal Gesture Intelligence)

MMGI is a real-time human-computer interaction system that converts hand gestures and voice commands into desktop actions through a mode-aware, safety-gated execution pipeline.

## 1. Project Overview

### Problem Statement
Traditional desktop interaction is keyboard/mouse dependent and not robust for touchless control scenarios such as hands-busy workflows, accessibility support, and smart control surfaces.

### Why This Solution Is Needed
Most gesture demos fail in practical usage because they lack runtime safety, overload control, and reliable execution gating. They detect gestures but do not engineer the full system required for stable real-time control.

### MMGI Approach
MMGI combines computer vision, multimodal command input, runtime policy control, and UI observability into a single production-oriented architecture:
- Gesture input: MediaPipe + OpenCV
- Voice input: threaded listener with command normalization
- Safety gates: activation protocol, confidence checks, face authorization
- Action layer: centralized executor for OS-level commands
- UI layer: PyQt6 dashboard with live runtime state and diagnostics

---

## 2. System Architecture

MMGI is organized as a layered runtime pipeline with explicit separation between acquisition, decisioning, policy enforcement, and execution.

### High-Level Flow
1. Camera frame acquisition via OpenCV
2. Hand landmark detection using MediaPipe
3. Gesture classification from finger-state features
4. Decision resolution using mode-aware mappings
5. Runtime and security policy checks
6. Action dispatch through a centralized executor
7. State propagation to UI via SharedState signals

### Runtime Pipeline
Input (Gesture / Voice)
-> Input Event Normalizer
-> DecisionEngine (mode map + whitelist)
-> RuntimeController (confidence/cooldown policy)
-> FaceSecurityManager (when enforced)
-> ActionExecutor
-> SharedState + UI + logs

---

## 3. Engineering Design

### Modular Architecture
MMGI uses clear component boundaries:
- core: sensing and perception primitives (camera, hand tracking, gesture classification, voice, face security)
- engine: control and decision components (activation, decision engine, unified pipeline, execution)
- ui: dashboard rendering, runtime worker thread, shared state model
- utils: configuration and logging infrastructure

### Separation of Concerns
- Detection is isolated from classification logic.
- Classification is isolated from mode/action decisioning.
- Decisioning is isolated from execution side effects.
- Execution is centralized to maintain policy consistency and auditability.

### Key Design Decisions
- QThread worker for real-time pipeline to keep PyQt UI responsive.
- SharedState signal bus for low-coupling UI updates.
- Unified event model so gesture and voice follow the same policy path.
- Bounded queue and stale-frame drop strategy to maintain responsiveness under load.
- Explicit runtime states (RUNNING, PAUSED, ERROR) to support predictable failure behavior.

---

## 4. Execution Flow

### End-to-End Operation
1. WorkerThread reads frames from camera.
2. HandTracker extracts landmarks and confidence.
3. GestureClassifier resolves a gesture label.
4. DecisionEngine maps gesture or voice command to action/mode intent.
5. ActivationManager and RuntimeController verify readiness, confidence, cooldown, and lock state.
6. FaceSecurityManager gates sensitive actions when policy is active.
7. ActionExecutor performs OS-level behavior (application launch, media key, input control).
8. SharedState publishes updates to Vision panel, System panel, and Activity log.

### Example
Two Fingers in Media Mode -> DecisionEngine maps to volume_down -> runtime checks pass -> ActionExecutor sends volume down command.

### Multimodal Fusion
Gesture and voice are normalized into a common InputEvent representation before policy and decision processing, ensuring consistent behavior across modalities.

---

## 5. Performance and Latency

### Real-Time Targets
- Camera pipeline configured around real-time inference cadence.
- FPS is tracked continuously and exposed in UI.
- Per-frame latency is logged for runtime diagnostics.

### Optimization Strategy
- Bounded queue to prevent unbounded buffering.
- Stale-frame dropping to prioritize freshest user intent.
- Inference rate cap and frame-time budget controls.
- Short-lived gesture cache to maintain continuity across dropped frames.

### Practical Runtime Characteristics
Observed runtime logs show low tens-of-milliseconds frame processing in healthy conditions, with graceful degradation under load rather than hard blocking.

---

## 6. Failure Handling and Reliability

MMGI is built to fail safely and recover predictably.

### Failure Handling
- Camera failures: retry and recovery loop with runtime state transition.
- Gesture model failures: fallback and component reinitialization path.
- Voice failures: backoff and retry window to avoid thrashing.
- Face authorization failures: action blocking and explicit security status.

### Stability Strategies
- Confidence-based rejection for low-quality detections.
- Activation/deactivation protocol to prevent accidental actions.
- Cooldown and lock states to control rapid repeats.
- Structured log channels for runtime and performance telemetry.

---

## 7. Features

- Real-time gesture recognition using MediaPipe landmarks and OpenCV frame processing.
- Multimodal command support (gesture + voice) through a unified decision pipeline.
- Mode-aware command system: App Mode, Media Mode, System Mode.
- Face-based authorization gate for protected execution contexts.
- Runtime fail-safe states surfaced in UI (LOW_CONFIDENCE, AUTH_REQUIRED, COOLDOWN).
- Latency-aware backpressure controls using bounded queueing and stale-frame dropping.
- Live PyQt6 dashboard with activity timeline, runtime controls, and diagnostics.
- Headless CLI mode for non-UI operation and automation scenarios.

---

## 8. Installation and Usage

### Prerequisites
- Python 3.10+
- Windows 10/11 recommended
- Webcam
- Microphone (for voice module)

### Installation
    git clone https://github.com/<your-username>/MMGI.git
    cd MMGI
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

Place hand_landmarker.task in the project root before running.

### Run Dashboard Mode
    python main.py

### Run Headless Mode
    python main.py --headless

### Run Dedicated CLI Mode
    python cli/main.py

### Common CLI Options
- --mode app|media|system
- --max-frames N (0 means run until interrupted)

Example:
    python cli/main.py --mode media --max-frames 600

---

## 9. Configuration and Runtime Controls

MMGI supports JSON-driven runtime configuration and UI-based live tuning.

### Configuration Files
- config/gesture_map.json
- config/user_config.json
- config/calibration.json
- config/face_security.json
- config/voice_control.json

### Runtime Controls
- Toggle face security, voice listener, and gesture control.
- Manual mode selection.
- Detection confidence and gesture confirmation sliders.
- Calibration controls for hold durations and sensitivity.

Changes are persisted and applied with minimal runtime disruption.

---

## 10. Testing and Validation

MMGI includes integration-oriented pytest coverage for:
- Gesture-to-action resolution behavior
- Multimodal fusion pathways
- Runtime lock and safety-gate conditions
- Pipeline lifecycle behavior
- Logging and telemetry correctness

Run tests:
    python -m pytest -q

---

## 11. Future Improvements

- Adaptive per-user threshold personalization from historical usage.
- Enhanced offline voice intent parsing for noisy environments.
- Stronger cross-platform action abstraction beyond Windows-centric automation.
- Session replay and diagnostics export for reproducible failure analysis.
- Policy tuning dashboard with comparative latency and false-activation trends.

---

## 12. License

Educational and academic use.
