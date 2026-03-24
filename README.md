# MMGI (Multi-Modal Gesture Intelligence)

Real-time touchless desktop control with gestures, voice commands, and face-secured actions.

## Overview
MMGI is an offline human-computer interaction system that converts webcam hand tracking and microphone input into desktop actions. It combines gesture recognition, mode-aware decision logic, face authorization, and centralized execution in one production-oriented pipeline.

### Technical Summary
- Input channels: Gesture (MediaPipe + OpenCV), Voice (SpeechRecognition)
- Decision core: Mode-aware DecisionEngine with action whitelists
- Security: Face authorization gate for System Mode actions
- Execution: Central ActionExecutor (mouse, keyboard, media)
- UI: PyQt6 dashboard with live status, activity log, and settings

---

## Features
### Gesture Control
- Real-time hand landmark tracking
- Stable gesture confirmation and low-confidence rejection
- Activation gate and cooldowns to prevent accidental triggers

### Voice Commands
- Normalized voice commands through the same decision pipeline as gestures
- Unmapped transcript feedback for debugging
- Error backoff to avoid repeated recognition thrash

### Face-Based Security
- System Mode action authorization with allow/deny checks
- Unauthorized actions blocked before execution
- Presence-aware status feedback in UI

### Mode Switching
- App Mode, Media Mode, System Mode
- Gesture and voice mode-switch support
- Cooldown-protected switching

---

## Phase 3 Engineering Upgrades

### 1. Lifecycle Management
A dedicated lifecycle layer now manages pipeline state transitions.

States:
- STOPPED
- STARTING
- RUNNING
- STOPPING
- ERROR

Supported operations:
- Start pipeline
- Stop pipeline gracefully
- Restart pipeline safely

UI controls:
- Header Start / Stop / Restart buttons

Key module:
- ui/pipeline_lifecycle.py

### 2. Fault Handling
Implemented runtime handling for:
- Camera not detected: retry loop with bounded attempts and delay
- No hand detected: periodic error logging and safe no-action path
- Voice recognition failures: recovery window/backoff with status updates

### 3. Fallback Safety Mechanisms
- Action suppression when input confidence is uncertain
- Temporary safety lock when uncertainty streak is high
- Existing activation/deactivation gate preserved and enforced

---

## Architecture

## Runtime Pipeline
Input (Gesture / Voice)
-> Input Event Normalizer
-> DecisionEngine (mode map + whitelist)
-> Security Layer (FaceAuthorization for System Mode)
-> Mode Manager
-> Action Executor
-> Shared State + UI + Logs

## Modular Structure
- core/
  - calibration.py
  - hand_tracking.py
  - gesture_classifier.py
  - face_security.py
  - voice_control.py
- engine/
  - decision_engine.py
  - unified_pipeline.py
  - action_executor.py
  - metrics_manager.py
  - activation_manager.py
- ui/
  - pipeline_lifecycle.py
  - worker_thread.py
  - shared_state.py
  - ui.py
- utils/
  - logger.py
  - config.py

## Lifecycle Pseudocode
```python
lifecycle = PipelineLifecycleManager()

if lifecycle.start(worker_factory):
    while lifecycle.state == "RUNNING":
        frame = camera.read()
        if not frame:
            handle_camera_fault()
            continue

        event = normalize_inputs(gesture_input, voice_input)
        decision = decision_engine.decide(event)

        if decision.requires_security:
            if not face_security.authorize(frame):
                log_denied_action(decision)
                continue

        action_executor.execute(decision.action)

lifecycle.stop(timeout_ms=3500)
```

---

## Logging System

### Format
Default runtime format:
- [HH:MM:SS] LEVEL: message

Files:
- logs/mmgi.log (runtime events/errors)
- logs/metrics_report.jsonl (periodic reliability metrics)

### Logged Event Categories
- Face authorization (allowed / denied)
- Gesture detection
- Voice command recognition (mapped / unmapped / error)
- Lifecycle transitions (start/stop/restart/error)
- Runtime errors and safety lock activations

### Example Log Output
```text
[19:04:11] INFO: Lifecycle: stage=pipeline status=started details=Worker loop active
[19:04:13] INFO: Gesture detected: Two Fingers
[19:04:13] INFO: Voice command: command=volume_up mapped=True details=recognized
[19:04:14] INFO: Face auth: allowed=False status=Unknown User X similarity=0.421
[19:04:14] WARNING: Low confidence gesture (confidence=0.53)
[19:04:15] ERROR: Safety lock active due to uncertain gesture input
```

---

## Debugging and Reliability

### UI Debug Strategies
- Active mode indicator in header and vision panel
- Current gesture + final action display
- Face authorization status text and color
- Voice/mic status indicator
- Activation lock status with explicit lock reason (face/security/gesture stability)
- Optional debug overlay on camera feed

### Runtime Controls (Settings)
The Settings tab in the PyQt6 dashboard now provides interactive UI controls for system configuration:

**Security Section:**
- Enable/disable face security at runtime with toggle
- Activate and capture authorized face from live camera feed

**Runtime Controls Section:**
- Toggle face security on/off at runtime
- Toggle voice listener on/off at runtime
- Toggle gesture control on/off at runtime
- Manual mode selector (App / Media / System) for forced mode changes

**Detection & Response Section** (NEW - ConfigManager Integrated):
- **Hand Detection Confidence Slider** (0.50–0.95):
  - Controls hand detection confidence threshold
  - Instant update to `user_config.json` (thresholds.hand_detection_confidence)
  - Lower values accept more hand poses; higher values are stricter
  - Default: 0.70
  
- **Gesture Confirmation Frames Slider** (2–20 frames):
  - Controls how many consecutive frames a gesture must be stable before confirmation
  - Instant update to `user_config.json` (smoothing.gesture_confirmation_frames)
  - Lower values = faster response; higher values = more stable/deliberate
  - Default: 4 frames

**Calibration Section:**
- Gesture hold time, stability frames, and cursor sensitivity sliders
- Calibration wizard for automatic hand distance estimation

All slider changes are:
- ✓ **Instantly saved** to `config/user_config.json`
- ✓ **Immediately reflected** in the running pipeline (DecisionEngine subscribers notified)
- ✓ **No restart required** — changes take effect instantly
- ✓ **Thread-safe** — ConfigManager handles atomic file updates and notifications

### Latency and Backpressure Controls
The pipeline now enforces bounded work under load:
- Bounded frame queue to avoid unbounded memory growth
- Stale-frame dropping to keep inference on fresh input
- Fixed inference-rate cap (default: 30 FPS)
- Per-frame processing budget; over-budget frames skip action stage
- Latest stable gesture cache for short continuity across dropped/late frames

Config keys (defaults in code):
- `pipeline.frame_queue_size` (default: 4)
- `pipeline.drop_stale_frames` (default: true)
- `pipeline.max_inference_fps` (default: 30.0)
- `pipeline.frame_time_budget_ms` (default: 33.0)
- `pipeline.latest_gesture_ttl_s` (default: 0.25)

---

## User Configuration System

### Overview
MMGI now provides a runtime-configurable system that allows you to customize gesture/voice mappings, confidence thresholds, and timing parameters without modifying code or restarting.

### Configuration Files

#### `config/user_config.json` (User-editable)
This is the main configuration file that you can edit to customize MMGI behavior. It stores:
- **Gesture mappings**: per-mode gesture → action mappings
- **Voice mappings**: per-mode voice command → action mappings
- **Thresholds**: hand detection, tracking, and face similarity confidence
- **Smoothing**: gesture confirmation, mode switch timing, cooldown values

### ConfigManager Class
The `ConfigManager` (in [core/config_manager.py](core/config_manager.py)) manages all user configuration:

**Key Features:**
- Load/Save: Loads `config/user_config.json` on startup; saves changes atomically
- File Watching: Background thread detects manual file edits and reloads automatically
- Subscribers: Components (DecisionEngine, etc.) subscribe to config changes for live updates
- Thread-Safe: All operations protected by locks for concurrent access
- Validation: Validates all actions against ALLOWED_ACTIONS whitelist

### DecisionEngine Integration
DecisionEngine now integrates with ConfigManager for dynamic gesture/voice mapping:

```python
from core.config_manager import ConfigManager
from engine.decision_engine import DecisionEngine

# Create and integrate ConfigManager
config = ConfigManager()
engine = DecisionEngine(config_manager=config)

# Changes are picked up automatically — no restart required!
config.set_gesture_mapping("App Mode", "Two Fingers", "open_youtube")
```

### Runtime Configuration Updates

**Option A: Programmatic** – Call from code:
```python
config.set_gesture_mapping("Media Mode", "Three Fingers", "mute")
config.set("thresholds", "hand_detection_confidence", 0.85)
```

**Option B: Manual editing** – Edit `config/user_config.json` directly, then save. ConfigManager detects changes and reloads automatically (if file watching is enabled via `config.start_watch()`).

### Examples
See [examples/config_integration_example.py](examples/config_integration_example.py) for comprehensive usage examples.

### Calibration Verification UX
- Live camera preview in Settings (same annotated feed as Vision panel)
- Per-gesture verification flow: Open Palm, Pinch, Three Fingers Hold
- Test Gesture action with pass/fail feedback using confidence + stability checks
- Live verification telemetry: confidence, hand distance estimate, gesture status

### State Tracking
- SharedState broadcasts live pipeline values
- Lifecycle state is shown in activity log
- Calibration and metrics are exposed as UI signals

### Reliability Metrics to Track
- Gesture accuracy percent
- False activation rate percent
- Average response latency (ms)
- Mode switches per minute

Sample metrics JSON line:
```json
{"timestamp":"2026-03-22T19:32:41","gesture_accuracy_pct":87.5,"false_activation_rate_pct":8.33,"avg_response_latency_ms":41.2,"mode_switches_per_min":3.0}
```

---

## Installation

## Prerequisites
- Python 3.10+
- Windows 10/11 recommended
- Webcam
- Microphone (for voice module)

## Setup
```bash
git clone https://github.com/<your-username>/MMGI.git
cd MMGI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Required model file:
- Place hand_landmarker.task in project root

---

## How to Run

### Dashboard Mode
```bash
python main.py
```

### Headless Mode
```bash
python main.py --headless
```

### Dedicated CLI Headless Mode
```bash
python cli/main.py
```

CLI options:
- `--mode` (app | media | system): set initial runtime mode
- `--max-frames` (int): auto-exit after N frames (0 = run until Ctrl+C)

Examples:
```bash
python cli/main.py --mode system
python cli/main.py --mode media --max-frames 600
```

---

## Controls and Commands

### Global Controls
- Open Palm (hold): activate
- Fist: deactivate
- Three Fingers (hold): cycle mode

### App Mode
- One Finger: open browser
- Two Fingers: open music app

### Media Mode
- One Finger: volume up
- Two Fingers: volume down
- Four Fingers: play/pause
- Thumbs Up: mute

### System Mode
- Face authorization required before sensitive actions
- Voice and gesture commands routed through same decision pipeline

---

## System Requirements
- CPU: modern dual-core or better
- RAM: 8 GB recommended
- Camera: 720p recommended
- OS: Windows 10/11
- Python packages:
  - mediapipe
  - opencv-python
  - pyautogui
  - PyQt6
  - SpeechRecognition
  - bcrypt

---

## Limitations
- Performance depends on lighting and camera quality
- Speech recognition accuracy varies by microphone and ambient noise
- Desktop automation behavior can differ across OS/application contexts
- Face matching is environment-sensitive (angle, illumination)

---

## Future Improvements
- Noise-robust voice parser with offline command model
- Adaptive per-user gesture threshold learning
- Better cross-platform action abstraction layer
- Session replay + diagnostics exporter
- Confidence-aware multimodal fusion tuning

---

## License
Educational / academic use.
