# MMGI Project Overview — Smart Mode AI Dashboard
## Architecture & Component Guide

This document explains what every file does in the MMGI project.

---

## 🎯 Project Purpose

MMGI converts hand gestures from a webcam into real system actions through a 3-mode Smart Mode system, all visualised in a premium PyQt6 AI dashboard.

---

## 🗂 Component Map

```
main.py ─────────────────────────────────────────── Entry point
  ├── run_dashboard()  →  PyQt6 AI Dashboard (default)
  └── run_headless()   →  OpenCV terminal-only mode (--headless)

shared_state.py ─────── Reactive data store (PyQt6 signals)
worker_thread.py ───────QThread: full pipeline on background thread

ui/
  main_window.py ─────── Top-level QMainWindow, assembles all panels
  sidebar.py ─────────── Collapsible nav sidebar (Vision + Mode)
  vision_panel.py ─────── Live camera feed + gesture overlay + stability bar
  system_panel.py ─────── System card + Mode card + Performance card
  activity_log.py ─────── Horizontal scrollable pill event timeline
  styles.py ──────────── QSS stylesheet tokens (colours, cards, buttons)

core/
  camera.py ──────────── Webcam capture (OpenCV VideoCapture)
  hand_tracking.py ────── MediaPipe HandLandmarker Tasks API
  gesture_classifier.py ─ Rule-based finger-state → gesture name

engine/
  activation_manager.py ─ Safety gate (Open Palm hold to activate)
  decision_engine.py ───── Smart Mode action resolver + mode switching
  action_executor.py ────── pyautogui system action execution

config/
  gesture_map.json ─────── Mode-based gesture → action config

utils/
  config.py ──────────── Dot-key YAML-like config loader
  fps_counter.py ─────── Rolling-window FPS counter
```

---

## 🔁 Data Flow (per frame)

```
Camera.read_frame()
    │
    ▼
HandTracker.detect_hands()   ← MediaPipe AI inference
HandTracker.get_hands_info() ← Struct: {right, left, count}
    │
    ▼
GestureClassifier.classify(finger_states)
    → gesture name string  e.g. "Thumbs Up"
    │
    ▼
DecisionEngine.process(gesture)
    ├── is_mode_switch?  → update mode stability, commit after 1 s
    └── else             → get_action(gesture, mode)  → action string
    │
    ▼
ActivationManager.update(gesture)
    ├── Open Palm 2 s → ACTIVE
    ├── Fist          → INACTIVE
    └── returns should_execute: bool
    │
    ▼ (if should_execute and action)
ActionExecutor.execute(action)
    → pyautogui keyboard, subprocess, etc.
    │
    ▼
SharedState.set_*(...)   ← signals broadcast to all UI panels
WorkerThread.frame_ready.emit(QImage)
    │
    ▼
VisionPanel.update_frame()   ← UI repaints with annotated frame
```

---

## 🧩 Key Components

### `shared_state.py` — Reactive Store
Central `QObject` holding all live data (fps, mode, gesture, etc.).
Every field has a typed `pyqtSignal` that fires on change.
UI panels subscribe independently — zero coupling between pipeline and UI.

### `worker_thread.py` — QThread Pipeline
Runs the full MMGI pipeline on a background thread so the UI never freezes.
Emits `frame_ready(QImage)` and `error(str)`.
Calls `SharedState.set_*()` to push telemetry to connected UI widgets.

### `engine/decision_engine.py` — Smart Mode Engine
- Loads `config/gesture_map.json` — `mode_switch`, `App Mode`, `Media Mode`, `System Mode` sections
- `process(gesture)` → `(action | None, mode_changed_bool)`
- Mode switching: 10-frame stability + 1.0 s hold + 1.5 s cooldown
- Mode-switch gesture (`Three Fingers` → `next_mode`) is never forwarded as an action
- `mode_stability_progress` (0–1) drives the stability bar in VisionPanel

### `config/gesture_map.json` — Mode Mappings
```json
{
  "mode_switch":  {"Three Fingers":"next_mode"},
  "App Mode":     {
    "One Finger":"open_brave",
    "Two Fingers":"open_apple_music",
    "Thumbs Up":"open_youtube",
    "Thumb, Index, Middle and Ring":"close_window"
  },
  "Media Mode":   {
    "One Finger":"volume_up",
    "Two Fingers":"volume_down",
    "Thumb and Index":"next_track",
    "Thumb, Index and Middle":"prev_track",
    "Four Fingers":"play_pause",
    "Thumbs Up":"mute"
  },
  "System Mode":  {
    "Thumb and Index":"scroll_up",
    "Thumb, Index and Middle":"scroll_down",
    "Two Fingers":"left_click",
    "Thumb, Index, Middle and Ring":"right_click"
  }
}
```

Note: Cursor movement has been intentionally removed from System Mode.

### `ui/main_window.py` — Dashboard Layout
```
Header (52 px)   ◉ MMGI  Smart Mode AI Controller        APP MODE  ⬤ INACTIVE
Body (stretch)   Sidebar (220 px) | Vision (flex) | System Panel (280 px)
Footer (76 px)   Activity Log — scrollable horizontal pill timeline
```

### `ui/vision_panel.py` — Live Feed
- Receives `QImage` from `WorkerThread.frame_ready` signal
- Scales image to fill label with aspect-ratio preserved
- Glow border changes colour with current mode / active state
- Mode-switch stability progress bar at the bottom

### `ui/system_panel.py` — Right Panel (3 cards)
- **SystemCard**: ON/OFF indicator badge + toggle button (visual feedback)
- **ModeCard**: current mode name + per-mode gesture → action instruction table; mode-switch reminder at bottom
- **PerformanceCard**: FPS, latency, volume bar, confidence bar — all live via SharedState signals

### `ui/activity_log.py` — Event Timeline
Horizontal scrollable strip of coloured pills.
Each pill: `● [HH:MM:SS]  CATEGORY  description`
Categories: ACTION (cyan), MODE (green), SYSTEM (grey), ERROR (red).
Auto-scrolls right on new events. Keeps max 200 events.

### `ui/sidebar.py` — Collapsible Navigation
220 px expanded / 56 px collapsed with animated width transition.
Tabs: Vision, Mode.
Collapse button with ◄/► arrow, smooth `QPropertyAnimation`.

### `ui/styles.py` — Qt Stylesheet
Global QSS injected at `QApplication` level.
Colour tokens: `BG_DEEP #0F0F14`, `BG_CARD #1A1A22`, `ACCENT #00E5FF`, `ACTIVE #00FF88`, `INACTIVE #FF4466`.

---

## ⚡ Activation Protocol

| Step | Gesture | Duration | Effect |
|------|---------|----------|--------|
| Activate | Open Palm | 2 seconds | System → ACTIVE (green) |
| Deactivate | Fist | Instant | System → INACTIVE |
| Switch Mode | Three Fingers | 1 second hold | Cycle to next mode |
| Execute Action | Any mode gesture | Instant (1 per 1 s cooldown) | Runs system action |

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 ≥ 6.7 | UI framework |
| mediapipe ≥ 0.10 | Hand AI model |
| opencv-python ≥ 4.10 | Camera capture + frame processing |
| pyautogui ≥ 0.9 | Keyboard / media key automation |
| numpy ≥ 2.3 | Array operations for MediaPipe |

---

## 7. System Reliability Engineering

The MMGI system is designed as a coordinated, non-blocking runtime where UI rendering and sensor inference are separated by thread boundaries. The PyQt6 dashboard runs on the main GUI thread, while the real-time pipeline runs inside a dedicated QThread (`WorkerThread`). This separation prevents OpenCV capture, MediaPipe inference, and action dispatch from stalling repaint events or making controls unresponsive under load.

Reliability is achieved through a reactive state contract implemented by `SharedState`. Instead of direct widget mutation from pipeline code, MMGI writes canonical runtime values (mode, gesture confidence, lock states, latency, fail-safe state) into `SharedState`, which emits typed Qt signals to subscribed panels. This architecture isolates acquisition and inference from presentation, minimizes race-prone cross-widget dependencies, and enables safe runtime state transitions such as `RUNNING`, `PAUSED`, and `ERROR` without UI deadlock.

At the coordination layer, MMGI combines `ActivationManager`, `DecisionEngine`, `RuntimeController`, `ModeManager`, and `UnifiedDecisionPipeline`. Each component owns one responsibility: gesture stability and activation gating, gesture-to-action resolution, runtime permission checks, mode transition policy, and end-to-end event orchestration. This explicit ownership model reduces side effects and makes the system predictable during safety-critical transitions like face-authorization loss or camera recovery.

## 8. Latency Control and Backpressure Strategy

The MMGI system uses bounded buffering and controlled discard semantics to preserve interactivity during transient overload. Camera frames are pushed into a bounded queue (`deque`) configured with `maxlen=5` in the performance profile, which prevents unbounded memory growth and guarantees upper-bounded queueing delay.

```python
frame_queue = deque(maxlen=frame_queue_size)
```

When inference falls behind, MMGI applies a latest-frame policy: stale frames are dropped so decision logic operates on current user intent rather than delayed history. This matters for gestures such as `Two Fingers` in Media mode, where acting on old frames produces perceived lag and user-visible inconsistency.

MMGI also enforces a per-frame processing budget (`frame_time_budget_ms`) and tracks budget pressure as a runtime signal. Rather than freezing execution, the worker uses hysteresis-based overload detection and recovery detection to avoid oscillation noise. The combination of bounded queue, stale-frame dropping, and frame-budget governance keeps latency bounded while preserving responsiveness of gesture-to-action execution.

## 9. Failure Handling and Recovery

Camera reliability is handled with startup retries and runtime recovery loops. If frame reads fail repeatedly, MMGI moves runtime state to `ERROR`, logs the condition, releases camera resources, and attempts controlled reopen cycles before resuming processing. This avoids hard crashes and allows recovery from transient camera disconnects.

Face authorization is enforced as a runtime gate in the MMGI system when the policy is active, preventing unsafe action execution under unauthorized conditions. If authorization is lost while active, MMGI force-deactivates execution and surfaces a security lock state to both logs and UI. The worker also supports reinitialization of the face module after repeated evaluation faults.

Low-confidence handling is explicit. Gesture confidence below the configured threshold does not proceed to action dispatch; instead, MMGI marks uncertain input, updates fail-safe indicators (for example `LOW_CONFIDENCE`), and requires re-stabilization before execution resumes. This reduces false activations caused by noisy landmarks.

Model failures are treated as recoverable faults. If hand detection or gesture classification throws repeated exceptions, MMGI rebuilds the tracking/classification components and transitions runtime state through a paused recovery window. Logging is structured by severity (`INFO`, `WARNING`, `ERROR`) with runtime and performance channels, enabling post-run diagnosis of overload, security, and model health.

## 10. End-to-End Execution Flow

In real-time operation, the MMGI system executes the following chain for each accepted input frame:

Camera -> MediaPipe hand inference -> Gesture classification -> DecisionEngine -> FaceSecurityManager policy gate -> ActionExecutor -> OS action

An example path in Media mode is: `Two Fingers` is detected and stabilized, `DecisionEngine` resolves it to `volume_down`, runtime gates verify readiness, and `ActionExecutor` dispatches the mapped OS-level command through PyAutoGUI.

Multimodal fusion is handled by normalizing both gesture and voice into a shared `InputEvent` format before pipeline decisioning. This allows MMGI to combine channels coherently (gesture + voice), apply conflict resolution, and preserve a single authorization and runtime policy surface regardless of modality.

```python
gesture_event = InputEventNormalizer.from_gesture(...)
voice_event = InputEventNormalizer.from_voice(...)
result = unified_pipeline.process_event(event, frame_bgr=frame, enforce_face_security=...)
```

## 11. Integration Validation

Integration validation in the MMGI system is implemented with pytest suites that exercise behavior across component boundaries instead of isolated unit-only checks. Gesture-to-action resolution is validated by feeding representative gesture events through decision and pipeline layers and asserting expected actions, mode transitions, and blocked-state outcomes.

Fusion behavior is validated by tests that inject gesture and voice events with controlled timing and confidence, ensuring multimodal resolution and deduplication policies behave consistently under realistic sequencing. These tests verify that the same runtime pipeline correctly handles single-modality and mixed-modality traffic.

Authorization gating is validated using mocks/stubs for face-security outcomes and execution spies for action dispatch. Tests assert that unauthorized states block execution while authorized states permit execution, which confirms that security policy enforcement is not bypassed during overload or mode transitions.

## 12. User Configuration and UI Feedback

The MMGI system externalizes operational behavior through JSON configuration (gesture maps, thresholds, smoothing, security, and voice settings). This allows evaluator-visible reproducibility and environment-specific tuning without source code edits.

Runtime updates are propagated through `SharedState` and signal-driven UI bindings. As worker values change, UI panels receive immediate updates for mode, confidence, activation lock, runtime state, and fail-safe status. This architecture makes internal runtime decisions observable and debuggable from the dashboard in real time.

UI controls (including sliders and toggles in the settings flow) are connected to runtime configuration paths so operators can tune confidence, smoothing, and behavior without restarting the MMGI system. User-facing state chips explicitly expose safety and execution context (`LOW_CONFIDENCE`, `AUTH_REQUIRED`, `COOLDOWN`, runtime state), which improves transparency and supports production-style monitoring during demonstrations.
