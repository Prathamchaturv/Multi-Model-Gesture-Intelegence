# MMGI Codebase Architecture & Components Analysis

## Overview
MMGI is a multimodal gesture and voice controlled interface system with face-based security. The architecture follows a unified pipeline pattern:

```
Input (Gesture / Voice)
    ↓
InputEventNormalizer
    ↓
DecisionEngine (resolve command to action)
    ↓
SecurityLayer (FaceSecurityManager)
    ↓
ModeManager (enforce mode switching)
    ↓
ActionExecutor (execute system action)
```

---

## 1. DecisionEngine Class

**Location:** `engine/decision_engine.py`

### Key Signatures

```python
class DecisionEngine:
    def __init__(
        self,
        config_path: str | Path | None = None,
        stability_frames: int = STABILITY_FRAMES,  # default 10
        hold_seconds: float = HOLD_SECONDS,        # default 1.0
        cooldown_seconds: float = COOLDOWN_SECONDS, # default 2.0
        config_manager: ConfigManager | None = None,
    )
```

### Input Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `config_path` | `Path` | `config/gesture_map.json` | User gesture mappings |
| `stability_frames` | `int` | 10 | Frames needed for mode stability |
| `hold_seconds` | `float` | 1.0 | Hold duration for mode detection |
| `cooldown_seconds` | `float` | 2.0 | Minimum time between mode switches |
| `config_manager` | `ConfigManager` | None | Runtime config updater |

### Core Methods

#### **`process(gesture: str | None) → tuple[str | None, bool]`**
- **Legacy path** for backward compatibility
- Returns: `(action_name, mode_changed_flag)`
- Handles gesture-only classification (no voice)

#### **`decide(event, mode: str | None = None) → DecisionOutcome`**
- **Modern path** for normalized events
- Input: `InputEvent(type, command, confidence, timestamp)`
- Returns: `DecisionOutcome(action=str|None, target_mode=str|None, reason=str|None)`

#### **`process_event(event: InputEvent) → DecisionOutcome`**
- Resolves gesture/voice command to action within current mode
- Applies mode stability logic (STABILITY_FRAMES + HOLD_SECONDS)
- Returns `DecisionOutcome` with action or target_mode

### Decision Logic Flow

```python
# 1. Check if gesture is mode switch trigger
if is_mode_switch(gesture):
    # Accumulate stability frames & hold time
    # Return (None, True) when stable and held long enough
    
# 2. Reset stability counter if NOT mode switch
# 3. Lookup action in mode-specific gesture map
# 4. Validate action against whitelist
# 5. Return (action, False)
```

### State Variables

```python
self.current_mode: str              # 'App Mode' | 'Media Mode' | 'System Mode'
self._candidate_mode: str | None    # Mode in transition
self._stable_count: int             # Frames holding same gesture
self._hold_start: float             # Timestamp of hold start
self._last_switch_time: float       # Cooldown tracking
```

### Mode Switching

Three **MODES**:
- `'App Mode'` - Default, for launching applications
- `'Media Mode'` - Media player control (volume, play/pause, tracks)
- `'System Mode'` - Air-mouse cursor control

**Trigger:** `Three Fingers` gesture → cycles modes

**Stability Requirement:**
```python
# Must satisfy BOTH conditions:
1. stable_count >= STABILITY_FRAMES (10)  # OR hold_seconds elapsed
2. time_held >= HOLD_SECONDS (1.0)        # consistent hold time
```

### Decision Maps Loaded

```python
_action_maps[mode][gesture] → action
_voice_action_maps[mode][command] → action
_mode_switch_map[gesture] → target_mode
_action_whitelist[mode] → set of allowed actions
```

---

## 2. ActionExecutor Class

**Location:** `engine/action_executor.py`

### Class Signature

```python
class ActionExecutor:
    def __init__(self, config: dict | None = None)
```

### Configuration

```python
config = {
    'brave_path': r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe',
    'apple_music_aumid': 'AppleInc.AppleMusicWin_nzyj5cx40ttqa!App',
}
```

### Public Methods

#### **`execute(action: str) → None`**
- **Main execution endpoint**
- Applies rate-limiting:
  - **Global cooldown:** 1.0s minimum between ANY actions
  - **Per-action cooldown:** 1.0s minimum for same action
  - **Returns silently if cooldown active**

#### **`display_action(frame) → frame`**
- Renders fading action label at bottom of frame (2.5s duration)
- Alpha blends from 1.0 → 0.0

### Action Implementations

| Action | Implementation |
|--------|-----------------|
| `open_brave` | `subprocess.Popen([brave_path])` |
| `open_apple_music` | `subprocess.Popen(['explorer.exe', f'shell:AppsFolder\\{aumid}'])` |
| `open_youtube` | `webbrowser.open('https://www.youtube.com', new=2)` |
| `open_browser` | Same as `open_youtube` |
| `close_window` | `pyautogui.hotkey('alt', 'f4')` |
| `switch_tab` | `pyautogui.hotkey('ctrl', 'tab')` |
| `scroll_down` | `pyautogui.scroll(-420)` |
| `left_click` | `pyautogui.click(button='left')` |
| `right_click` | `pyautogui.click(button='right')` |
| `double_click` | `pyautogui.doubleClick()` |
| `play_pause` | `pyautogui.press('playpause')` |
| `volume_up` | `pyautogui.press('volumeup')` |
| `volume_down` | `pyautogui.press('volumedown')` |
| `mute` | `pyautogui.press('volumemute')` |
| `next_track` | `pyautogui.press('nexttrack')` |
| `prev_track` | `pyautogui.press('prevtrack')` |

### Allowed Actions (ALLOWED_ACTIONS frozenset)

**App Mode:**
```
open_brave, open_apple_music, open_browser, open_music, open_youtube,
close_window, switch_tab, scroll_down
```

**Media Mode:**
```
play_pause, pause_media, next_track, prev_track, previous_track,
volume_up, volume_down, mute
```

**System Mode:**
```
All of above + left_click, right_click, double_click
```

---

## 3. Camera Class

**Location:** `core/camera.py`

### Class Signature

```python
class Camera:
    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        camera_index: int = 0,
    )
```

### Lifecycle Methods

```python
open() -> bool           # Open webcam, return success
release() -> None        # Release resources
is_opened() -> bool      # Check if currently opened
read_frame() -> (bool, frame)  # Read one BGR frame
```

### Properties

```python
camera.width: int        # 1280
camera.height: int       # 720
```

### Usage Pattern

```python
camera = Camera(width=1280, height=720, fps=30)
if camera.open():
    while running:
        success, frame = camera.read_frame()
        if success:
            process(frame)
finally:
    camera.release()
```

---

## 4. HandTracker Class

**Location:** `core/hand_tracking.py`

### Class Signature

```python
class HandTracker:
    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_path: str | None = None,  # hand_landmarker.task
    )
```

### Core Methods

#### **`detect_hands(frame) → HandLandmarkerResult`**
- Runs MediaPipe inference on BGR frame
- Returns raw MediaPipe result object

#### **`get_hands_info(results) → dict`**
Returns structured hand data:
```python
{
    'count': 0|1|2,
    'left': {
        'landmarks': [(x, y, z), ...],  # 21 landmark tuples (0-1 normalized)
        'finger_states': {
            'thumb': bool,
            'index': bool,
            'middle': bool,
            'ring': bool,
            'pinky': bool,
        },
        'handedness': 'Left' | 'Right',
        'confidence': 0.0-1.0,
    },
    'right': { ... }  # or None
}
```

### Finger Detection Logic

| Finger | Detection Method |
|--------|-----------------|
| **Thumb** | Extended if: `|thumb_tip.x - wrist.x| > |thumb_ip.x - wrist.x|` |
| **Index/Middle/Ring/Pinky** | Extended if: `tip.y < pip.y` (tip higher on screen) |

### Landmark Indices (MediaPipe)

- **0:** Wrist
- **1-4:** Thumb (ip → pip → mcp → tip)
- **5-8:** Index (mcp → pip → ip → tip)
- **9-12:** Middle (mcp → pip → ip → tip)
- **13-16:** Ring (mcp → pip → ip → tip)
- **17-20:** Pinky (mcp → pip → ip → tip)

### Visualization Methods

```python
draw_landmarks(frame, results) → frame      # Draw skeleton
display_hand_detection(frame, hands_info) → frame  # Hand count badge
display_finger_states(frame, states) → frame       # Finger up/down display
close() → None                                      # Release MediaPipe
```

---

## 5. GestureClassifier Class

**Location:** `core/gesture_classifier.py`

### Class Signature

```python
class GestureClassifier:
    pass  # Stateless utility class
```

### Core Method

#### **`classify(finger_states: dict) → str`**

**Input:** `{'thumb': bool, 'index': bool, 'middle': bool, 'ring': bool, 'pinky': bool}`

**Output:** Gesture name string

### Recognized Gestures

| Gesture | Pattern | Used For |
|---------|---------|----------|
| `Open Palm` | All fingers extended | Activation |
| `Fist` | All fingers curled | Deactivation |
| `Thumbs Up` | Only thumb extended | Action trigger |
| `One Finger` | Only index extended | Pointing / action |
| `Two Fingers` | Index + middle only | Peace sign / scroll |
| `Three Fingers` | Index + middle + ring | **Mode switch** |
| `Four Fingers` | All except thumb | Media control |
| `Thumb, Index, Middle and Ring` | Thumb + index + middle + ring | Alternative gesture |
| `Pinky` | Pinky only | Alternative gesture |
| `Unknown` | No match | Invalid/transitional state |

### Classification Logic

```python
_PATTERNS = [
    ('Open Palm', {'thumb': True, 'index': True, 'middle': True, 'ring': True, 'pinky': True}),
    ('Fist', {'thumb': False, 'index': False, 'middle': False, 'ring': False, 'pinky': False}),
    # ... etc
]

# Ordered pattern matching (most-specific first)
# For each pattern: if all specified fingers match → return gesture
# If no pattern matches → return 'Unknown'
```

### Visualization

```python
display_gesture(frame, gesture: str, position='center|left|right') → None
```

---

## 6. VoiceControl Integration

**Location:** `core/voice_control.py`

### Class Signature

```python
class VoiceCommandListener:
    def __init__(
        self,
        enabled: bool = True,
        listen_timeout_s: float = 1.2,
        phrase_time_limit_s: float = 2.0,
        poll_sleep_s: float = 0.05,
        energy_threshold: int = 250,
        recognition_language: str = 'en-IN',
    )
```

### Supported Backends

1. **PyAudio** (preferred)
   - Uses `speech_recognition.Microphone()`
2. **SoundDevice** (fallback)
   - Direct audio capture if PyAudio unavailable

### Key Methods

```python
start() → None              # Start background listener thread
stop() → None               # Stop listener, join thread
poll_latest() → VoiceCommandEvent | None  # Get newest command
```

### Output Format

```python
@dataclass
class VoiceCommandEvent:
    command: str            # Normalized command token
    transcript: str         # Full recognized text
    timestamp: float        # Unix timestamp
```

### Voice Command Normalization

Maps recognized text to command tokens:

```python
'play_song' | 'pause' → 'play_pause'
'next_track' | 'previous_track' → navigation
'volume up' | 'volume down' → volume control
'open brave' | 'open youtube' → app launch
'close window' | 'switch tab' → window control
'scroll down' → scroll control
```

### Thread Safety

- **Background thread** runs `_run()` method
- Commands queued in `queue.Queue(maxsize=32)`
- `poll_latest()` drain + return newest non-blocking

---

## 7. MultiModal Fusion

### Layer 1: MultimodalFusionLayer

**Location:** `engine/multimodal_fusion.py`

```python
@dataclass
class FusionPolicy:
    voice_priority: bool = True                    # Voice takes precedence
    suppress_unstable_gesture_on_voice: bool = True  # Drop weak gestures if voice present
    duplicate_window_s: float = 0.3                # Time window for dedup
    allow_parallel_non_duplicate: bool = False     # Allow simultaneous gesture+voice

def merge(
    gesture_event: InputEvent | None,
    voice_event: InputEvent | None,
    gesture_is_stable: bool,
    uncertainty_lock_active: bool,
) → list[InputEvent]
```

**Merge Logic:**
```python
# 1. If voice present → add voice to output
# 2. If voice present AND gesture unstable → suppress gesture
# 3. If voice_priority AND near-duplicate → suppress gesture (unless voice)
# 4. Otherwise → add gesture if present
```

### Layer 2: MultiModalFusionEngine (Media Mode Authorization)

**Location:** `engine/multimodal_fusion.py`

```python
class MultiModalFusionEngine:
    def __init__(
        self,
        required_actions: set[str] = {'play_pause', 'mute'},
        action_voice_map: dict[str, set[str]] = {...},
        command_ttl_s: float = 2.5,
    )

    def update_voice(self, command: str, ts: float | None = None) → None
    
    def resolve(
        self,
        action: str | None,
        mode: str,
        ts: float | None = None,
    ) → tuple[bool, str | None]  # (allow_execute, matched_voice_cmd)
```

**Media Mode Voice Requirement:**
- **Required actions** for voice confirmation: `play_pause`, `mute`
- **TTL (time-to-live):** 2.5 seconds
- **Matching:** Voice command must match action's expected voice tokens

**Example:**
```python
# Gesture says: play_pause
# Last voice command: 'play_song' (within 2.5s, matches play_pause requirement)
# Result: (True, 'play_song') → ALLOW

# OR gesture says: volume_up
# No voice requirement for volume_up
# Result: (True, None) → ALLOW immediately
```

---

## 8. Face Security Authorization

**Location:** `core/face_security.py`

### Class Signature

```python
class FaceSecurityManager:
    def __init__(
        self,
        enabled: bool = True,
        authorized_image_path: str = 'config/authorized_face.jpg',
        authorized_encoding_path: str = 'config/authorized_face_encoding.json',
        similarity_threshold: float = 0.84,
        similarity_hysteresis: float = 0.05,
        min_detection_confidence: float = 0.6,
        eval_interval_s: float = 0.08,
        away_delay_s: float = 2.5,
        return_confirm_s: float = 0.7,
        unlock_confirm_s: float = 0.45,
        lock_confirm_s: float = 0.6,
    )
```

### Core Method

#### **`evaluate(frame_bgr) → FaceAuthResult`**

**Returns:**
```python
@dataclass
class FaceAuthResult:
    is_authorized: bool         # System may execute actions
    status_text: str            # UI display string
    face_detected: bool         # Face visible in frame
    user_present: bool          # System knows user is there
    system_paused: bool         # True if user away
    similarity: float | None    # 0.0-1.0 or None
```

### Authorization Logic

```
User Status Transitions:
─────────────────────
PRESENT (authorized = True)
  ├─ No face for > away_delay_s (2.5s)
  └─ → AWAY (system_paused = True, is_authorized = False)

AWAY (authorized = False)
  ├─ Face detected (similarity > return_confirm threshold)
  └─ Hold >  return_confirm_s (0.7s)
  └─ → RETURN_DETECTED (system_paused = False, is_authorized = False)

RETURN_DETECTED
  ├─ High similarity (> unlock_threshold, 0.45s hold)
  └─ → PRESENT (is_authorized = True)
```

### Similarity Thresholds

- **Unlock threshold:** `similarity_threshold` (default 0.84)
- **Lock threshold:** `similarity_threshold - hysteresis` (default 0.79)
  - Prevents oscillation on borderline similarity

### Face Encoding

- **Detector:** OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`)
- **Encoding:** Lightweight grayscale texture features
- **Storage:** JSON file with numpy array serialization
- **Distance metric:** Cosine similarity (persisted as pre-normalized vectors)

### Evaluation Interval

- **`eval_interval_s`:** (default 0.08s = 125ms)
- Skips re-evaluation if called more frequently
- Returns cached `_stable_result` from previous evaluation

---

## 9. Unified Pipeline Orchestration

**Location:** `engine/unified_pipeline.py`

### InputEvent Normalization

```python
@dataclass(frozen=True)
class InputEvent:
    type: str           # 'gesture' | 'voice'
    command: str        # Gesture name or voice command
    confidence: float   # 0.0-1.0
    timestamp: float    # Unix timestamp

class InputEventNormalizer:
    @staticmethod
    def from_gesture(gesture: str, confidence: float, timestamp: float | None = None) → InputEvent
    
    @staticmethod
    def from_voice(command: str, confidence: float = 1.0, timestamp: float | None = None) → InputEvent
```

### UnifiedDecisionPipeline

```python
class UnifiedDecisionPipeline:
    def __init__(
        self,
        decision_engine: DecisionEngine,
        action_executor: ActionExecutor,
        mode_manager: ModeManager,
        face_security: FaceSecurityManager | None = None,
        conflict_resolver: InputConflictResolver | None = None,
    )

    def process_event(
        self,
        event: InputEvent,
        frame_bgr=None,
        enforce_face_security: bool = True,
    ) → PipelineDecision
```

### Pipeline Flow

```
1. InputEvent received
   ↓
2. DecisionEngine.decide(event, current_mode)
   ├─ Mode switch? → Apply ModeManager cooldown, update mode
   ├─ Action? → Lookup in mode-specific maps
   └─ Return DecisionOutcome(action|mode_change|reason)
   ↓
3. Conflict Resolution
   ├─ Check InputConflictResolver for duplicates
   └─ Drop if duplicate within duplicate_window_s
   ↓
4. Face Security Check (if enabled and frame provided)
   ├─ FaceSecurityManager.evaluate(frame_bgr)
   ├─ is_authorized = True? → Continue
   └─ is_authorized = False? → Block action
   ↓
5. ActionExecutor.execute(action)
   ├─ Apply per-action cooldown
   ├─ Apply global cooldown
   └─ Execute (subprocess, pyautogui, webbrowser)
   ↓
6. Return PipelineDecision
   ├─ action: executed action or None
   ├─ mode_changed: bool
   ├─ mode: current mode after processing
   ├─ blocked_reason: 'face_unauthorized' | 'conflict_duplicate_ignored' | None
   └─ security_status: face eval text or None
```

---

## 10. Data Flow: Gesture → Voice → Action

### Example: Two Fingers (Media Mode)

```
1. GESTURE INPUT
   Camera frame
   ↓
   HandTracker.detect_hands(frame)
   → get_hands_info(results)
   → finger_states = {'thumb': False, 'index': True, 'middle': True, 'ring': False, 'pinky': False}
   ↓

2. CLASSIFY
   GestureClassifier.classify(finger_states)
   → 'Two Fingers'
   ↓

3. NORMALIZE
   InputEventNormalizer.from_gesture('Two Fingers', confidence=0.95, timestamp=100.50)
   → InputEvent(type='gesture', command='Two Fingers', confidence=0.95, timestamp=100.50)
   ↓

4. DECIDE
   DecisionEngine.decide(event, mode='Media Mode')
   → Lookup: _action_maps['Media Mode']['Two Fingers'] = 'volume_down'
   ↓

5. RESOLVE & EXECUTE
   UnifiedDecisionPipeline.process_event(event, frame_bgr)
   ├─ InputConflictResolver.should_drop(action, event) → False
   ├─ FaceSecurityManager.evaluate(frame_bgr) → is_authorized=True
   ├─ ActionExecutor.execute('volume_down')
   │  └─ pyautogui.press('volumedown')
   └─ Return PipelineDecision(action='volume_down', mode='Media Mode')
   ↓

6. UI FEEDBACK
   ActionExecutor.display_action(frame)
   → Render: "Action: Volume Down" (fading over 2.5s)
```

### Example: Voice Command + Gesture (Media Mode: play_pause)

```
1. VOICE INPUT (parallel thread)
   Microphone audio
   ↓
   VoiceCommandListener.poll_latest()
   → VoiceCommandEvent(command='play_song', transcript='..', timestamp=100.40)
   ↓
   InputEventNormalizer.from_voice('play_song')
   → InputEvent(type='voice', command='play_song', confidence=1.0, timestamp=100.40)

2. GESTURE INPUT (main thread)
   ... (same as above)
   → InputEvent(type='gesture', command='Four Fingers', confidence=0.90, timestamp=100.50)

3. FUSION LAYER
   MultimodalFusionLayer.merge(
       gesture_event=... ('Four Fingers'),
       voice_event=... ('play_song'),
       gesture_is_stable=True,
       uncertainty_lock_active=False,
   )
   → Policy: voice_priority=True
   → Return [voice_event]  (suppress gesture if unstable)

4. DECIDE
   DecisionEngine.decide(voice_event, mode='Media Mode')
   → Lookup: _voice_action_maps['Media Mode']['play_song'] = 'play_pause'
   ↓

5. FUSION ENGINE (Media Mode Authorization)
   MultiModalFusionEngine.resolve(
       action='play_pause',
       mode='Media Mode',
       ts=100.50,
   )
   → action='play_pause' in required_actions
   → _last_command='play_song' matches expected {'play_song', 'pause'}
   → Return (True, 'play_song')
   ↓

6. EXECUTE
   ActionExecutor.execute('play_pause')
   → pyautogui.press('playpause')
```

---

## 11. Test Structure

**Location:** `tests/` directory

### Test Files & Coverage

| Test File | Component | Coverage |
|-----------|-----------|----------|
| `test_gesture_classifier.py` | `GestureClassifier` | Pattern matching, edge cases |
| `test_action_executor.py` | `ActionExecutor` | Action execution, cooldown |
| `test_unified_pipeline.py` | `UnifiedDecisionPipeline` | End-to-end flow, conflict resolution |
| `test_face_security.py` | `FaceSecurityManager` | Authorization logic, hysteresis |
| `test_voice_control.py` | `VoiceCommandListener` | Background thread, command polling |
| `test_multimodal_fusion.py` | `MultimodalFusionLayer` | Event merging, prioritization |
| `test_multimodal_fusion_layer.py` | `MultimodalFusionEngine` | Media mode voice requirement |
| `test_mode_switching.py` | `DecisionEngine` mode logic | Mode transition, cooldown |
| `test_adaptive_gesture_learning.py` | `AdaptiveGestureLearning` | Dynamic gesture calibration |
| `test_calibration_metrics.py` | Calibration system | Metrics collection |
| `test_logging.py` | Logging utilities | Log output |
| `test_login_security.py` | Face+password auth | Login flow |
| `test_pipeline_lifecycle.py` | Pipeline startup/shutdown | Lifecycle events |
| `test_shared_state_runtime_controls.py` | Shared state management | Runtime control sync |
| `test_system_cursor_control.py` | `AirMouseController` | Cursor movement, clicks |

### Test Patterns

#### Pattern 1: Mock Objects
```python
class _SpyExecutor(ActionExecutor):
    def __init__(self):
        super().__init__()
        self.executed: list[str] = []
    
    def execute(self, action: str) → None:
        self.executed.append(action)

# Usage in tests
executor = _SpyExecutor()
pipeline = UnifiedDecisionPipeline(..., action_executor=executor)
pipeline.process_event(event)
assert executor.executed == ['expected_action']
```

#### Pattern 2: Fixture Setup with Temporary Files
```python
def _make_manager(enabled: bool = True, threshold: float = 0.84):
    td = tempfile.TemporaryDirectory()
    base = Path(td.name)
    encoding_path = base / 'authorized_face_encoding.json'
    
    mgr = FaceSecurityManager(
        enabled=enabled,
        authorized_encoding_path=str(encoding_path),
        # ... other params
    )
    return mgr, encoding_path
```

#### Pattern 3: Input Event Testing
```python
def test_decision_engine_voice_mapping_for_media_mode() → None:
    engine = DecisionEngine()
    event = InputEventNormalizer.from_voice('play_song', timestamp=101.0)
    outcome = engine.decide(event, mode='Media Mode')
    assert outcome.action == 'play_pause'
    assert outcome.reason is None
```

### Test Execution

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_gesture_classifier.py -v

# Run specific test function
python -m pytest tests/test_gesture_classifier.py::TestGestureClassifier::test_open_palm -v

# Direct execution (for standalone tests)
python tests/test_gesture_classifier.py
```

---

## 12. Configuration Management

**Location:** `core/config_manager.py` & `config/` directory

### Config Files

```
config/
├── gesture_map.json           # Mode → gesture → action mappings
├── voice_control.json         # Mode → voice command → action mappings
├── user_config.json           # User preferences & customizations
├── users.json                 # User account management
├── face_security.json         # Face auth settings
├── authorized_face_encoding.json  # Reference face encoding
├── custom_gestures.json       # Learned custom gestures
├── calibration.json           # Calibration parameters
├── gesture_map.json           # Current gesture bindings
└── custom_gestures.json       # User-defined gestures
```

### Runtime Reloading

**DecisionEngine** subscribes to `ConfigManager` changes:
```python
self._config_manager.subscribe(self._on_config_change)

def _on_config_change(self, change: ConfigChange) → None:
    if change.section in ('gesture_mappings', 'voice_mappings', '*'):
        self._load_from_config_manager()
        print('[DecisionEngine] Reloaded gesture/voice mappings')
```

---

## 13. Key Interactions Summary

| From | To | Data | Method |
|------|-----|------|--------|
| Camera | HandTracker | BGR frame | `detect_hands(frame)` |
| HandTracker | GestureClassifier | finger_states dict | `classify(finger_states)` |
| GestureClassifier | DecisionEngine | gesture string | `decide(InputEvent)` |
| VoiceCommandListener | DecisionEngine | voice command | `decide(InputEvent)` |
| DecisionEngine | UnifiedPipeline | DecisionOutcome | `process_event(event)` |
| UnifiedPipeline | FaceSecurityManager | BGR frame | `evaluate(frame_bgr)` |
| UnifiedPipeline | ActionExecutor | action string | `execute(action)` |
| ActionExecutor | System | pyautogui/subprocess | media keys, apps |
| System | ActionExecutor | N/A | visual feedback via display_action |
| ConfigManager | DecisionEngine | config changes | callback `_on_config_change` |

---

## 14. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      INPUT SOURCES                              │
│  ┌──────────────┐              ┌──────────────────┐             │
│  │   Camera     │              │  Microphone      │             │
│  └──────┬───────┘              └────────┬─────────┘             │
│         │                               │                       │
│         v                               v                       │
│  ┌──────────────┐              ┌──────────────────────┐         │
│  │ Hand Tracker │              │ Voice Command        │         │
│  │ (MediaPipe)  │              │ Listener (Background)│         │
│  └──────┬───────┘              └────────┬─────────────┘         │
│         │                               │                       │
│         v                               v                       │
│  ┌──────────────────┐         ┌─────────────────────┐           │
│  │Gesture           │         │Voice Command Event  │           │
│  │Classifier        │         │                     │           │
│  └──────┬───────────┘         └────────┬────────────┘           │
│         │                              │                        │
│         └──────────────┬───────────────┘                        │
│                        │                                        │
│                        v                                        │
│            ┌──────────────────────┐                            │
│            │  Input Event         │                            │
│            │  Normalizer          │                            │
│            └────────┬─────────────┘                            │
│                     │                                          │
└─────────────────────┼──────────────────────────────────────────┘
                      │
        ┌─────────────v──────────────┐
        │  Multimodal Fusion Layer   │
        │  (Dedup, Priority, Gate)   │
        └─────────────┬──────────────┘
                      │
        ┌─────────────v──────────────┐
        │  Decision Engine           │
        │  (Mode, Gesture→Action)    │
        └─────────────┬──────────────┘
                      │
        ┌─────────────v──────────────────────┐
        │  Conflict Resolver                 │
        │  (Drop near-duplicates)            │
        └─────────────┬──────────────────────┘
                      │
        ┌─────────────v──────────────────────┐
        │  Face Security Manager             │
        │  (Authorize if present & matched) │
        └─────────────┬──────────────────────┘
                      │
        ┌─────────────v──────────────────────┐
        │  Action Executor                   │
        │  (Rate-limited system actions)    │
        └─────────────┬──────────────────────┘
                      │
        ┌─────────────v──────────────────────┐
        │  System Output                     │
        │  • pyautogui (keyboard/mouse)     │
        │  • subprocess (applications)      │
        │  • webbrowser (URLs)              │
        └───────────────────────────────────┘
```

---

## 15. Performance Characteristics

| Component | Latency | Notes |
|-----------|---------|-------|
| HandTracker (MediaPipe) | ~30-50ms | Per-frame inference |
| GestureClassifier | ~1ms | Rule-based pattern matching |
| DecisionEngine | ~2ms | Map lookup + validation |
| FaceSecurityManager | ~30-50ms | Haar cascade + feature extraction |
| ActionExecutor | ~10-100ms | Depends on OS response time |
| **Total Pipeline** | **~100-200ms** | End-to-end per frame |

---

## 16. Thread Safety

### Thread Model

```
Main Thread (UI / Pipeline Loop)
├─ Camera.read_frame()
├─ HandTracker.detect_hands()
├─ DecisionEngine.process()
└─ ActionExecutor.execute()

Voice Thread (Background)
├─ VoiceCommandListener._run()
├─ Queues VoiceCommandEvent
└─ Main thread polls via poll_latest()

ConfigManager Thread (Background, if applicable)
└─ Notifies DecisionEngine of config changes
```

### Synchronization

- **VoiceCommandListener:** Uses `queue.Queue` (thread-safe)
- **DecisionEngine:** Uses `threading.RLock` for config updates
- **ActionExecutor:** Tracks `_last_executed` dict (single-threaded access)
- **No shared mutable state** between main and background threads

---

## 17. Key File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `core/camera.py` | ~90 | Webcam lifecycle |
| `core/hand_tracking.py` | ~280 | MediaPipe hand detection |
| `core/gesture_classifier.py` | ~150 | Pattern-based gesture recognition |
| `core/voice_control.py` | ~300 | Background speech recognition |
| `core/face_security.py` | ~400 | Face-based authorization gate |
| `engine/decision_engine.py` | ~450 | Gesture/voice→action resolution |
| `engine/action_executor.py` | ~250 | System action execution |
| `engine/unified_pipeline.py` | ~200 | End-to-end orchestration |
| `engine/multimodal_fusion.py` | ~150 | Gesture+voice deduplication |
| `tests/test_unified_pipeline.py` | ~150 | Integration tests |
| `tests/test_gesture_classifier.py` | ~100 | Gesture classification tests |
| `tests/test_face_security.py` | ~150 | Authorization tests |

---

*End of MMGI Codebase Architecture Document*
