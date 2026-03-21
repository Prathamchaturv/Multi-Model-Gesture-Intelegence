# MMGI — Multi-Modal Gesture Intelligence

<p align="center">
  <strong>Touch-free desktop control through real-time hand gesture recognition.</strong><br/>
  A rule-based, fully offline gesture control system built with Python and MediaPipe.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python"/>
  <img src="https://img.shields.io/badge/MediaPipe-0.10%2B-orange" alt="MediaPipe"/>
  <img src="https://img.shields.io/badge/PyQt6-6.7%2B-green" alt="PyQt6"/>
  <img src="https://img.shields.io/badge/OpenCV-4.10%2B-red" alt="OpenCV"/>
  <img src="https://img.shields.io/badge/Architecture-Rule--Based-lightblue" alt="Architecture"/>
  <img src="https://img.shields.io/badge/License-Educational-lightgrey" alt="License"/>
</p>

---

## Table of Contents

1. [Overview](#1--overview)
2. [Project Context](#project-context)
3. [Screenshots](#2--screenshots)
4. [Features](#3--features)
5. [Architecture](#4--architecture)
6. [Project Structure](#5--project-structure)
7. [Technology Stack](#6--technology-stack)
8. [Installation](#7--installation)
9. [How to Run](#8--how-to-run)
10. [Gesture Reference](#9--gesture-reference)
11. [Testing](#10--testing)
12. [Performance Metrics](#11--performance-metrics)
13. [Privacy & Security](#12--privacy--security)
14. [Innovation Highlights](#13--innovation-highlights)
15. [Future Scope](#14--future-scope)
16. [Author](#15--author)
17. [License](#16--license)

---

## 1 · Overview

**MMGI (Multi-Modal Gesture Intelligence)** is a real-time, touch-free desktop control
system that uses an ordinary webcam as its only input device. It tracks 21 hand landmarks
per frame using Google's MediaPipe HandLandmarker model, classifies hand configurations
into named gestures via a deterministic rule-based classifier, and dispatches live system
actions — all running locally on the CPU with no network dependency.

The system operates across three contexts — **App Mode**, **Media Mode**, and **System Mode**
— each mapping the same gesture vocabulary to a different set of actions. A dedicated
**Smart Mode Switching** engine lets the user cycle between contexts with a single held
gesture, multiplying the command space without requiring additional gestures to be learned.

**MMGI is an academic mini-project** demonstrating applied human-computer interaction (HCI)
engineering: perception, classification, decision logic, action execution, and a reactive
PyQt6 dashboard are implemented as clearly separated, independently testable layers.

### Design Principles

- **No ML classifier** — gesture recognition is entirely deterministic, based on computed
  finger extension states derived from landmark geometry
- **Fully offline** — the MediaPipe model file ships with the project; no network call is
  made per frame or at runtime
- **Rule-based architecture** — all decision logic is explicit, readable, and auditable
- **Safety-gated activation** — the system requires a deliberate hold gesture before
  executing any actions, preventing accidental triggers

## Project Context

This project was developed individually as a full-stack AI desktop system focused on
real-time gesture recognition and touch-free human-computer interaction.

The codebase intentionally keeps perception, decision logic, system control, and UI in
separate modules so each part can be tested and improved independently. The implementation
emphasizes deterministic behavior, low-latency feedback, and practical desktop safety
controls (activation gates, cooldowns, and confidence-based filtering).

Development has been iterative: features such as gesture remapping, runtime logging,
mode-switch stability, and authentication hardening were added in small increments and
validated with tests to keep behavior predictable.

---

## 2 · Screenshots

### Dashboard — App Mode

<p align="center">
  <img src="assets/ui_dashboard_main.png" width="950">
</p>

> Three-panel layout: left sidebar (Vision / Mode navigation), centre live camera feed
> with gesture label and stability bar overlay, right info panel (System status, Mode map,
> Performance metrics, Volume and Confidence indicators). Activity Log timeline at the bottom.

---

## 3 · Features

### 3.1 Hand Gesture Recognition

- **Rule-based classifier** operating on the 5-finger extension state vector derived from
  MediaPipe 21-landmark output — no training data or model weights required
- Recognises **10 named gestures**: One Finger, Two Fingers, Three Fingers, Four Fingers,
  Open Palm, Fist, Thumbs Up, Pinky, Ring and Pinky, Unknown
- **Static gestures** (Open Palm, Fist, Thumbs Up, individual fingers) recognised per frame
- **Dynamic gestures**: Swipe Left and Swipe Right detected by tracking horizontal landmark
  displacement across a configurable frame window
- **Stability gate**: a gesture must be consistently held for ≥ 10 consecutive frames before
  it is promoted to a confirmed command, preventing single-frame noise from triggering actions
- Fully deterministic — identical inputs always produce identical outputs; no probabilistic
  inference involved

### 3.2 Smart Mode System

The core architectural concept of MMGI. Rather than assigning a fixed action to each gesture,
the system groups gestures into three **context modes**. The active mode determines how each
gesture is interpreted.

| Mode | Switch Trigger | Context |
|---|---|---|
| App Mode | Three Fingers held 1 s | Application control |
| Media Mode | Three Fingers held 1 s | Media playback |
| System Mode | Three Fingers held 1 s | Voice command control |

- **Mode switch trigger**: Three Fingers held continuously for 1 second (10-frame stability
  gate + 2.0 s post-switch cooldown to prevent immediate re-trigger)
- **Visual feedback**: a stability progress bar in the dashboard fills during the hold and
  resets on release
- **Conflict prevention**: no mode switch is processed during the cooldown window

### 3.3 App Mode

| Gesture | Action |
|---|---|
| 👍 Thumbs Up | Open Browser |
| ✌️ Two Fingers | Open VS Code |
| 🤙 Pinky | Close active window (`Alt+F4`) |
| 🤘 Ring and Pinky | Task switch (`Alt+Tab`) |

### 3.4 Media Mode

| Gesture | Action |
|---|---|
| 🖐️ Open Palm | Play / Pause (`MediaPlayPause`) |
| ☝️ One Finger | Next Track (`MediaNextTrack`) |
| ✌️ Two Fingers | Previous Track (`MediaPrevTrack`) |
| 👍 Thumbs Up | Volume Up |
| 🤙 Pinky | Volume Down |

Media Mode now runs inside the **unified multimodal event pipeline**.

- Gesture and voice commands are both normalized into a shared `InputEvent` payload.
- Both channels are resolved by the same `DecisionEngine` using mode-aware maps.
- A per-mode action whitelist is enforced before execution.
- Near-simultaneous duplicate triggers are deduplicated (voice can be prioritized).

### 3.5 System Mode 

- System gestures and System voice commands are both resolved through the same decision path.
- Typical system actions include left click, right click, double click, window control, and media keys.
- **Face-Based Security gate (System Mode only)**:
  - Face is checked immediately before executing every System Mode action
  - Current face is compared with a stored authorized user face encoding
  - Authorized -> action executes
  - Unauthorized / no-face -> action is blocked and logged with reason
- **Smart Presence Detection (System Mode only)**:
  - Presence monitor tracks whether any face remains visible
  - If no face is seen for a delay window, MMGI pauses System Mode
  - On return, presence must be stable briefly before resume (anti-flicker)
  - Dashboard feedback: `User Away - System Paused` and `User Detected - System Active`

### 3.6 Activation and Safety System

| Action | Trigger |
|---|---|
| Activate | Open Palm held for **2 seconds** |
| Deactivate | Fist (instant) |

- **Confidence threshold validation**: gestures below the MediaPipe detection confidence
  threshold are treated as Unknown and do not trigger any action
- **Activation hold timer**: the 2-second Open Palm hold prevents accidental activation
  when hands enter the camera frame incidentally
- System status broadcast in real time to all UI panels via `SharedState` PyQt6 signals

### 3.7 PyQt6 Dashboard

- Live camera feed panel with hand skeleton overlay and gesture label
- Mode indicator in header and right panel, colour-coded by active mode
- **Three active-mode indicator buttons** (APP / MEDIA / SYSTEM) highlight the current mode
- **Mode change banner** — a 1.8-second notification displayed above the camera feed whenever
  the mode switches (e.g. *Mode Changed → MEDIA MODE*)
- **Gesture detection feedback bar** showing the last detected gesture and the last executed
  action in real-time below the camera
- System status pill: ACTIVE / INACTIVE with contrasting colour cue
- Stability progress bar filling during Three-Finger mode-switch hold
- Rolling-window FPS counter and per-frame processing latency display
- Volume level and MediaPipe confidence percentage bars
- Timestamped activity log of gesture events and system state changes
- Collapsible sidebar with **Vision**, **Mode**, **Gestures**, and **Guide** navigation panels
- **Gesture Guide panel** (right side) — live list of all gesture→action mappings loaded
  directly from `gesture_map.json`
- `--headless` flag to run the pipeline with a plain OpenCV window instead of Qt

### 3.8 Custom Gesture Mapping

- **Gestures sidebar tab** displays a table-style editor with columns: **Gesture | Assigned Action | Edit**
- Clicking **Edit** switches the row into edit mode, revealing an action dropdown plus Save/Cancel
- Updated mappings are written back to `config/gesture_map.json` immediately
- `DecisionEngine` hot-reloads file changes at runtime, so new mappings execute without restarting

### 3.9 Adaptive Gesture Learning (Custom Training)

- **Train New Gesture** workflow in the Gestures tab:
  capture 25 valid hand frames (21 landmarks x/y/z), skipping frames where no hand is detected
- Landmark normalization is applied during training and inference:
  wrist-relative translation + scale normalization for position/size invariance
- Recorded frames are averaged into one stable reference pattern per custom gesture
- Custom gestures are saved in `config/custom_gestures.json` with:
  gesture name, normalized average landmark pattern, and assigned action
- Real-time matcher compares normalized live landmarks against saved patterns
  using mean Euclidean distance with configurable threshold
- Multi-frame confirmation gate (default 4 frames) prevents unstable one-frame triggers
- Runtime behavior: custom gestures are checked first; if none match, MMGI falls back to predefined gestures

### 3.9 In-App User Guide

- **Guide sidebar tab** provides beginner-friendly onboarding directly inside the app
- Includes clear steps for:
  activation (Open Palm hold), gesture usage best practices, and mode switching
- Displays a live gesture-to-action reference that updates after remapping changes

---

## 4 · Architecture

### System Architecture Diagram

<p align="center">
  <img src="assets/architecture.png" width="940" alt="MMGI system architecture diagram">
</p>

> The diagram summarizes how camera input flows through tracking, classification,
> decision logic, execution, and UI synchronization.

### Pipeline

```
Input (Gesture / Voice)
  -> Input Event Normalizer
  -> DecisionEngine (mode-aware mappings + per-mode whitelist)
  -> Security Layer (FaceSecurityManager for System Mode)
  -> ModeManager (APP / MEDIA / SYSTEM + switch cooldown)
  -> ActionExecutor
```

### Data Flow

```
Gesture frame stream and voice stream are both normalized to `InputEvent`.

Each event passes through one centralized path:

1. DecisionEngine resolves mode switch or action.
2. ModeManager commits switch events with cooldown protection.
3. Security layer authorizes System Mode actions using face verification.
4. ActionExecutor performs the final OS action.
5. SharedState/UI receives telemetry and logs.
```

### Layer Responsibilities

| Layer | Module | Responsibility |
|---|---|---|
| Input | `core/camera.py` | OpenCV `VideoCapture`, delivers raw BGR frames |
| Perception | `core/hand_tracking.py` | MediaPipe HandLandmarker wrapper, 21-landmark struct |
| Classification | `core/gesture_classifier.py` | Finger-state vector → gesture name string |
| Input Event | `engine/unified_pipeline.py` | `InputEvent` schema, event normalization, conflict handling |
| Decision | `engine/decision_engine.py` | Unified gesture/voice resolution, mode maps, per-mode whitelist |
| Mode | `engine/unified_pipeline.py` | `ModeManager` state and cooldown-protected mode switching |
| Security | `core/face_security.py` | Face authorization checks for System Mode actions |
| Safety | `engine/activation_manager.py` | Open Palm hold-to-activate, Fist-to-deactivate gate |
| Execution | `engine/action_executor.py` | `pyautogui` keyboard and media key dispatch |
| System Voice | `core/voice_control.py` | Speech recognition, normalization, and command token emission |
| State Bus | `ui/shared_state.py` | `QObject` reactive store; typed `pyqtSignal` per field |
| Pipeline | `ui/worker_thread.py` | Background `QThread` running the full per-frame loop |
| Dashboard | `ui/ui.py` | PyQt6 `QMainWindow` + all panels + QSS stylesheet |

---

## 5 · Project Structure

```
MMGI/
│
├── main.py                        # Entry point — Qt dashboard or --headless mode
├── requirements.txt               # All pip dependencies with minimum versions
├── hand_landmarker.task           # MediaPipe model file (must be placed manually)
│
├── config/
│   └── gesture_map.json           # Mode → gesture → action mapping (user-editable)
│   └── face_security.json         # System Mode face-auth gate configuration
│
├── core/                          # Perception layer — no Qt, no pyautogui imports
│   ├── camera.py                  # cv2.VideoCapture wrapper
│   ├── hand_tracking.py           # MediaPipe HandLandmarker Tasks API wrapper
│   ├── gesture_classifier.py      # Finger-state vector → gesture name (rule-based)
│   └── voice_control.py           # Voice command listener + phrase normalization
│
├── engine/                        # Decision and execution layer
│   ├── activation_manager.py      # Safety gate: hold Open Palm = ACTIVE
│   ├── decision_engine.py         # Smart Mode state machine + action resolver
│   └── action_executor.py         # pyautogui dispatch: keys, apps, media commands
│
├── ui/                            # All PyQt6 code
│   ├── shared_state.py            # Reactive store — QObject + pyqtSignal per field
│   ├── worker_thread.py           # QThread running the full pipeline loop
│   └── ui.py                      # MainWindow, Sidebar, VisionPanel, SystemPanel,
│                                  # GestureMapPanel, GestureGuideCard, ActivityLog, QSS
│
├── utils/
│   ├── config.py                  # Dot-key JSON config loader
│   ├── fps_counter.py             # Rolling-window FPS counter
│   └── logger.py                  # Async runtime logger → logs/mmgi.log
│
├── logs/
│   └── mmgi.log                   # Auto-created; gesture, action, warning, and error events
│
├── tests/
│   ├── test_gesture_classifier.py # Unit tests for GestureClassifier (14 cases)
│   ├── test_mode_switching.py     # Unit tests for DecisionEngine (31 cases)
│   └── test_action_executor.py    # Unit tests for ActionExecutor (16 cases)
│
└── assets/                        # Screenshots and diagrams
```

**Layer separation rationale**

- **`core/`** — perception only. No Qt, no pyautogui. Every class is unit-testable
  in a plain Python script without any UI dependency.
- **`engine/`** — decision and execution. Takes gesture name strings; returns action
  strings or fires system calls. No camera or MediaPipe imports.
- **`ui/`** — the only layer that imports Qt. `shared_state.py` is the single data bus;
  `worker_thread.py` bridges the pipeline to the UI; `ui.py` is the consolidated dashboard.
- **`config/gesture_map.json`** — the only file a non-developer needs to touch to remap
  any gesture to a different action.

---

## 6 · Technology Stack

| Component | Library | Version | Usage |
|---|---|---|---|
| Hand landmark AI | MediaPipe | ≥ 0.10 | 21-landmark detection, Tasks API, VIDEO mode |
| Image capture | OpenCV (`cv2`) | ≥ 4.10 | Webcam access, frame annotation |
| UI framework | PyQt6 | ≥ 6.7 | Dashboard, signals, background thread |
| Action automation | PyAutoGUI | ≥ 0.9.54 | Keyboard hotkeys, application launching |
| Password hashing | bcrypt | ≥ 5.0 | Secure local credential hashing and verification |
| Array operations | NumPy | ≥ 2.3 | Landmark coordinate arithmetic, EMA computation |
| Mouse control | `ctypes` (Win32) | stdlib | Raw cursor positioning and click event dispatch |
| Language | Python | 3.10+ | Core runtime |

All dependencies are pure-Python packages or ship pre-compiled wheels. No C extensions
need to be compiled from source.

---

## 7 · Installation

### Prerequisites

- Python 3.10 or later
- A working webcam (USB or built-in, any resolution ≥ 480p)
- Windows 10 / 11 recommended (voice and automation features validated on Windows)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/MMGI.git
cd MMGI

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows PowerShell
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place the MediaPipe model file in the project root
#    File name must be exactly:  hand_landmarker.task
#    Download from:
#    https://storage.googleapis.com/mediapipe-models/hand_landmarker/
#    hand_landmarker/float16/1/hand_landmarker.task
```

### `requirements.txt`

```
numpy>=2.3
opencv-python>=4.10
mediapipe>=0.10.30
pyautogui>=0.9.54
PyQt6>=6.7
bcrypt>=5.0
```

---

## 8 · How to Run

```bash
# Standard mode — Qt dashboard
python main.py

# Headless mode — OpenCV window only, no Qt
python main.py --headless
```

### Face Security Setup (Login)

1. Open the **Settings** tab in MMGI.
2. Under **Security**, enable **Face Security**.
3. Click **Activate + Capture Authorized Face** while your face is visible in the camera.
4. Restart MMGI once to apply the captured face encoding.
5. Use the `Face Recognition` option in login to authenticate with your enrolled face.

If no authorized face reference is available, face login is blocked by design.

Login hardening controls in `config/face_security.json`:
- `login_similarity_threshold`: first-stage similarity gate (default 0.93)
- `login_lbph_confidence_threshold`: second-stage LBPH distance gate (default 68.0, lower = stricter)
- `login_required_match_streak`: consecutive authorized frames required before access (default 3)
- `login_similarity_override_threshold`: very-high similarity fallback gate (default 0.975)
- `login_override_required_match_streak`: extra frames required when fallback gate is used (default 5)

### Voice Command Setup (System Mode)

Configure `config/voice_control.json`:
- `enabled`: enable/disable microphone listener
- `system_mode_only`: keep voice command execution limited to System Mode
- `system_mode_voice_actions`: map recognized voice tokens to action keys

Example spoken commands recognized:
- "open brave", "open apple music", "open youtube", "close window", "switch tab", "scroll down", "play song", "pause", "mute", "volume up", "volume down", "next track", "previous track"

Live voice status hints in dashboard:
- `Mic Active - Speak Command`: microphone capture backend is active.
- `Heard: ...`: speech was recognized but not mapped to an action token.
- `Voice Error: ...`: microphone/API/backend issue requiring configuration or permission fix.

### Quick Usage Checklist

1. Ensure webcam access is available to Python.
2. Launch with `python main.py` and complete login.
3. Choose one login option:
  - `User-Password` (username/password)
  - `Face Recognition` (camera-based face login)
4. If using face login first time, go to `Settings -> Security` after password login,
  enable Face Security, and capture your authorized face.
5. Restart MMGI once so the newly captured face reference is applied.
6. Hold **Open Palm** for 2 seconds to activate the controller.
7. Hold **Three Fingers** for 1 second to switch App / Media / System modes.
8. Use mode-specific gestures from the reference table below.

### Activation Sequence

| Step | Action | Result |
|---|---|---|
| 1 | Show **Open Palm** to camera, hold for **2 s** | Status turns ACTIVE (green) |
| 2 | Make a **Fist** | Instant deactivation, status INACTIVE |
| 3 | Hold **Three Fingers** for **1 s** | Mode cycles: App → Media → System → App |
| 4 | Use mode-specific gestures | Action fires; event appears in Activity Log |

> The system starts in **INACTIVE** state on every launch. The Open Palm activation
> step is required before any gesture commands are processed.

---

## 9 · Gesture Reference

### App Mode

| Gesture | Action |
|---|---|
| 👍 Thumbs Up | Open Browser |
| ✌️ Two Fingers | Open VS Code |
| 🤙 Pinky | Close Window (`Alt+F4`) |
| 🤘 Ring and Pinky | Task Switch (`Alt+Tab`) |

### Media Mode

| Gesture | Action |
|---|---|
| 🖐️ Open Palm | Play / Pause |
| ☝️ One Finger | Next Track |
| ✌️ Two Fingers | Previous Track |
| 👍 Thumbs Up | Volume Up |
| 🤙 Pinky | Volume Down |

### System Mode

| Gesture | Action |
|---|---|
| Voice Commands | Open Brave / Open YouTube / Close Window / Switch Tab / Scroll Down |

### Universal Gestures (all modes)

| Gesture | Action |
|---|---|
| 🖐️ Open Palm — 2 s hold | Activate system |
| ✊ Fist | Deactivate system |
| ✋ Three Fingers — 1 s hold | Cycle to next mode |

---

## 10 · Testing

Unit tests use the standard `unittest` framework and require no camera, Qt, or live system
calls — all external dependencies are patched with `unittest.mock`.

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific file
python -m pytest tests/test_gesture_classifier.py -v
python -m pytest tests/test_mode_switching.py -v
```

### Test Coverage

| Test File | Class Under Test | Cases | What is Verified |
|---|---|---|---|
| `test_gesture_classifier.py` | `GestureClassifier` | 14 | All 10 named gestures, edge cases, Unknown fallback |
| `test_mode_switching.py` | `DecisionEngine` | 31 | Mode transitions, stability gate, cooldown, debounce, hot-reload, action lookup |
| `test_action_executor.py` | `ActionExecutor` | 16 | Label completeness, action dispatch, cooldown behavior, feedback, edge cases |
| `test_logging.py` | `utils.logger` | 1 | Runtime log file creation and write path validation |

---

## 11 · Performance Metrics

### Runtime Benchmarks

Measured on a mid-range laptop (Intel Core i5, integrated webcam, no GPU acceleration):

| Metric | Typical Value | Notes |
|---|---|---|
| Pipeline FPS | 28 – 32 FPS | End-to-end: capture → landmark → classify → dispatch |
| Gesture latency | 35 – 50 ms | Frame capture to action execution |
| MediaPipe inference | 15 – 25 ms per frame | CPU, float16 model |
| UI render cycle | 5 – 10 ms | Qt signal → VisionPanel repaint |
| Activation hold | 2 000 ms | Required Open Palm hold duration |
| Mode switch hold | 1 000 ms | Required Three-Finger hold duration |
| Click cooldown | 500 ms | Prevents click spam on held gestures |
| Mode switch cooldown | 2 000 ms | Prevents immediate re-trigger after switch |

> Performance varies with webcam resolution, CPU load, and ambient lighting quality.

### Runtime Log File

MMGI writes runtime telemetry to **`logs/mmgi.log`** using an asynchronous queue-based logger
to avoid blocking the frame pipeline.

Each log line follows this format:

```
[18:09:49] INFO: Gesture detected: Two Fingers
[18:09:49] INFO: Action executed: Open Music
[18:09:50] WARNING: Low confidence gesture (confidence=0.58)
[18:09:51] ERROR: No hand detected
```

Event categories recorded:

| Level | Event |
|---|---|
| `INFO` | Gesture detected, action executed, pipeline start/stop |
| `WARNING` | Low confidence gesture |
| `ERROR` | No hand detected, invalid gesture, pipeline execution errors |

---

## 12 · Privacy & Security

- **All processing is local.** The webcam feed never leaves the device. No frames,
  landmarks, or gesture data are transmitted to any external server.
- **No telemetry.** MMGI contains no analytics, crash reporting, or usage tracking.
- **No persistent recording.** No video is stored to disk. The pipeline processes frames
  in memory and discards them immediately after use.
- **No network access.** The MediaPipe model runs entirely from the local file. The
  application makes no HTTP requests at runtime.
- **No elevated privileges.** MMGI runs as a standard user process. Win32 cursor and
  click calls operate at the application privilege level.
- **Explicit activation required.** The system remains INACTIVE until the user deliberately
  performs the Open Palm hold, preventing background gesture capture from affecting the
  desktop unintentionally.
- **Secure local authentication.** Login credentials are stored as bcrypt hashes in
  `config/users.json`; legacy SHA-256 hashes are migrated to bcrypt after successful login.
- **Runtime auth session gating.** Main dashboard access is only allowed while authenticated
  session state is valid during app runtime.
- **Gesture action rate limiting.** Action execution is globally throttled (1 second) and
  per-action throttled to prevent rapid repeated gesture-triggered commands.

---

## 13 · Innovation Highlights

### Context-Aware Gesture Mapping

The Smart Mode system decouples gesture identity from action semantics. The same physical
pose (e.g. Thumbs Up) maps to a different operation in each mode. This design multiplies
the effective command vocabulary without requiring users to learn additional gestures.

### Rule-Based Classifier with Zero Training Data

MMGI computes a 5-element boolean finger extension vector from MediaPipe landmark geometry
and pattern-matches it against a hand-authored lookup table. This makes the classifier
fully deterministic, immediately portable, transparent in failure mode (misclassified
gestures always map to "Unknown"), and trivially extendable without retraining.

### Voice-First System Mode

System Mode executes spoken commands (for example: open browser, switch tab,
close window) through a normalization layer plus action mapping, so System Mode
control remains hands-free without cursor tracking.

### Reactive UI via PyQt6 Signal Bus

`SharedState` is a `QObject` subclass with a typed `pyqtSignal` for every piece of
application state. The pipeline calls `set_*()` methods from the worker thread; all
connected UI widgets update automatically via Qt's thread-safe signal-slot mechanism.
No polling, no timers.

---

## 14 · Future Scope

### Multi-Modal Perception
Extend the perception layer with MediaPipe **FaceLandmarker** to detect brow raises or
eye winks as supplementary triggers, enabling hands-free interaction for accessibility use.

### Adaptive Gesture Thresholds
Replace hard-coded finger-state thresholds with a lightweight startup calibration pass.
The user performs each gesture once; the classifier learns per-user landmark distance
distributions, improving accuracy across hand sizes and lighting conditions.

### Performance Improvements
- Async double-buffer capture to decouple camera FPS from inference FPS
- Dedicated thread pool for MediaPipe inference to utilise multi-core CPUs more fully
- NumPy vectorisation of EMA and coordinate-mapping hot paths

### Extended Feature Set
- **Multi-hand chord gestures** for a richer two-handed command vocabulary
- **Dynamic gesture expansion** — Swipe Up / Down alongside Left / Right
- **Plugin action system** — allow `gesture_map.json` to reference user-defined Python
  callables rather than hard-coded action keys
- **Cross-platform mouse backend** — replace Win32 `ctypes` with `pynput` for macOS
  and Linux support
- **Gesture macro recording** — record landmark sequences and replay as automation scripts

---

## 15 · Author

**MMGI** was developed as an academic mini-project in applied human-computer interaction,
exploring touch-free desktop control through deterministic computer vision techniques.

---

## 16 · License

This project is intended for **educational and academic purposes only**.

It is not licensed for commercial use or redistribution. All third-party libraries
(MediaPipe, OpenCV, PyQt6, PyAutoGUI, NumPy) are used under their respective
open-source licences.

---

<p align="center">
  <sub>Built with Python · MediaPipe · PyQt6 · OpenCV</sub>
</p>

