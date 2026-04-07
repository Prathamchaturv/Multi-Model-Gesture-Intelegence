# MMGI Enhanced UI - Component Architecture Diagram

## System Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│ MainWindow (QMainWindow)                                                 │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Central Widget (QWidget)                                          │ │
│  │                                                                    │ │
│  │ ┌────────────┐     ┌───────────────────────────────────────────┐ │ │
│  │ │ Sidebar    │     │ Body Stack (QStackedWidget)              │ │ │
│  │ │            │     │                                           │ │ │
│  │ │ [VI]       │     │ Index 0: Main View (selected)            │ │ │
│  │ │ [GE]       │     │ ├─ Vision Panel (Camera)                 │ │ │
│  │ │ [MO]       │────→│ └─ SystemPanel (Right Sidebar) ◄────────┼─┼─┤
│  │ │ [LG]       │     │ Index 1: Gesture Mapping Panel           │ │ │
│  │ │ [ST]       │     │ Index 2: Help Panel                      │ │ │
│  │ │            │     │ Index 3: Settings Panel                  │ │ │
│  │ └────────────┘     │ Index 4: Logs Panel                      │ │ │
│  │                    └───────────────────────────────────────────┘ │ │
│  │                                                                    │ │
│  │ Tab Selection → Body Stack Index Change                           │ │
│  │                     (vision → 0)                                   │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │
                            System Panel
                                  │
                                  ▼
```

## SystemPanel Internal Architecture (NEW)

```
┌──────────────────────────────────────────────────────────┐
│ SystemPanel (QWidget)                                    │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ QVBoxLayout (outer)                               │ │
│  │                                                    │ │
│  │ ┌────────────────────────────────────────────────┐ │ │
│  │ │ QScrollArea (scroll)                           │ │ │
│  │ │                                                │ │ │
│  │ │ ┌──────────────────────────────────────────┐  │ │ │
│  │ │ │ Container QWidget (content)              │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ StatusCard (QFrame) ◄──── NEW      │   │  │ │ │
│  │ │ │ │                                    │   │  │ │ │
│  │ │ │ │ Gesture Indicator                  │   │  │ │ │
│  │ │ │ │ Voice Indicator                    │   │  │ │ │
│  │ │ │ │ Face Auth Indicator                │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ ControlPanel (QFrame) ◄──── NEW     │   │  │ │ │
│  │ │ │ │                                    │   │  │ │ │
│  │ │ │ │ Gesture Sensitivity Slider         │   │  │ │ │
│  │ │ │ │ Voice Confidence Slider            │   │  │ │ │
│  │ │ │ │ Mode Selection Buttons             │   │  │ │ │
│  │ │ │ │ Feature Toggles                    │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ SystemCard (QFrame)                │   │  │ │ │
│  │ │ │ │ (existing component)               │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ ModeCard (QFrame)                  │   │  │ │ │
│  │ │ │ │ (existing component)               │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ GestureGuideCard (QFrame)          │   │  │ │ │
│  │ │ │ │ (existing component)               │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ ┌────────────────────────────────────┐   │  │ │ │
│  │ │ │ │ PerformanceCard (QFrame)           │   │  │ │ │
│  │ │ │ │ (existing component)               │   │  │ │ │
│  │ │ │ └────────────────────────────────────┘   │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ │ [Stretch]                               │  │ │ │
│  │ │ │                                          │  │ │ │
│  │ │ └──────────────────────────────────────────┘  │ │ │
│  │ │ (Scrolls vertically if content exceeds view) │ │ │
│  │ │                                              │ │ │
│  │ └──────────────────────────────────────────────┘ │ │
│  │                                                  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                      │
│ Instance Variables:                                 │
│  _gesture_indicator: StatusIndicator               │
│  _voice_indicator: StatusIndicator                 │
│  _face_indicator: StatusIndicator                  │
│  _control_panel: ControlPanel                      │
│  _mode_card: ModeCard                              │
│  _guide_card: GestureGuideCard                     │
│                                                    │
└──────────────────────────────────────────────────────┘
```

## StatusIndicator Class Hierarchy

```
QWidget
  │
  └─ StatusIndicator
      │
      ├─ _dot (QLabel)
      │   └─ Shows colored indicator (●)
      │       Colors: ACTIVE, MODE_APP, MODE_MEDIA, TEXT_HINT
      │
      ├─ _value (QLabel)
      │   └─ Right-aligned value or status text
      │       Examples: "Thumbs Up", "open_brave", "Yes"
      │
      └─ Layout (QHBoxLayout)
          └─ [● Label] [stretch] [Value]

Public Methods:
  set_active(bool, value_text: str) → None
  set_status_color(str) → None

Usage Example:
  indicator = StatusIndicator('Gesture Detected', MODE_APP)
  indicator.set_active(True, 'Thumbs Up')
  state.gesture_changed.connect(
      lambda g: indicator.set_active(bool(g), g)
  )
```

## ControlPanel Class Hierarchy

```
QFrame
  │
  └─ ControlPanel
      │
      ├─ Gesture Sensitivity Section
      │   ├─ Label: "Gesture Sensitivity"
      │   ├─ _gest_slider (QSlider)
      │   │   Range: 30–100
      │   │   Normalized: 0.43–1.43x
      │   │   Output: normalized float
      │   ├─ _gest_val (QLabel)
      │   │   Display: "1.0x", "0.85x", etc.
      │   └─ Signal: gesture_sensitivity_changed
      │
      ├─ Voice Confidence Section
      │   ├─ Label: "Voice Confidence Threshold"
      │   ├─ _voice_slider (QSlider)
      │   │   Range: 30–100
      │   │   Normalized: 0.30–1.0
      │   │   Output: normalized float
      │   ├─ _voice_val (QLabel)
      │   │   Display: "0.60", "0.75", etc.
      │   └─ Signal: voice_confidence_changed
      │
      ├─ Mode Selection Section
      │   ├─ Label: "Operating Mode"
      │   ├─ _mode_btns (dict of QPushButton)
      │   │   "App Mode" → MODE_APP color
      │   │   "Media Mode" → MODE_MEDIA color
      │   │   "System Mode" → MODE_SYSTEM color
      │   │   Current: highlighted, others: outline
      │   └─ Signal: mode_requested
      │
      ├─ Feature Toggles Section
      │   ├─ _gest_enable (QCheckBox)
      │   │   Label: "Gesture"
      │   │   Signal: gesture_enabled_changed
      │   │
      │   └─ _voice_enable (QCheckBox)
      │       Label: "Voice"
      │       Signal: voice_enabled_changed
      │
      └─ Internal Methods:
          _on_gest_sensitivity_changed(int)
          _on_voice_confidence_changed(int)
          _on_mode_selected(str)
          _on_state_mode_changed(str)
          _connect_signals()

Signals Emitted:
  gesture_sensitivity_changed(float)
  voice_confidence_changed(float)
  mode_requested(str)
  gesture_enabled_changed(bool)
  voice_enabled_changed(bool)
```

## Signal Flow Architecture

```
INPUT LAYER (Hardware/User)
    │
    ├─ Camera → Hand Detection → WorkerThread
    │
    ├─ Microphone → Voice Recognition → WorkerThread
    │
    └─ User Input → SystemPanel Sliders/Buttons
                    ControlPanel Toggles

DATA LAYER
    │
    └─ SharedState (Central Hub)
        │
        ├─ Properties: gesture, voice, mode, face_auth, etc.
        │
        └─ Signals (broadcast):
            ├─ gesture_changed(str)
            ├─ voice_command_changed(str)
            ├─ face_auth_changed(bool, str)
            ├─ mode_changed(str)
            ├─ gesture_control_enabled_changed(bool)
            └─ voice_listener_enabled_changed(bool)

DISPLAY LAYER (UI Updates)
    │
    ├─ StatusIndicator (gesture)
    │   ├─ Connected to: gesture_changed signal
    │   └─ Updates: _on_gesture_updated()
    │
    ├─ StatusIndicator (voice)
    │   ├─ Connected to: voice_command_changed signal
    │   └─ Updates: _on_voice_updated()
    │
    ├─ StatusIndicator (face auth)
    │   ├─ Connected to: face_auth_changed signal
    │   └─ Updates: _on_face_updated()
    │
    ├─ ControlPanel (mode buttons)
    │   ├─ Connected to: mode_changed signal
    │   └─ Updates: _on_state_mode_changed()
    │
    └─ ControlPanel (sliders + toggles)
        ├─ Emits: gesture_sensitivity_changed
        ├─ Emits: voice_confidence_changed
        ├─ Emits: gesture_enabled_changed
        └─ Emits: voice_enabled_changed

ACTION LAYER (Optional)
    │
    └─ Application (wherever you connect the signals)
        ├─ _on_gesture_sensitivity_changed(float)
        │   → Update Config with new threshold
        │
        ├─ _on_voice_confidence_changed(float)
        │   → Update Config with new threshold
        │
        ├─ _on_mode_requested(str)
        │   → Already handled by mode button (→ SharedState)
        │
        ├─ gesture_enabled_changed.connect()
        │   → Already connected to state.set_gesture_control_enabled()
        │
        └─ voice_enabled_changed.connect()
            → Already connected to state.set_voice_listener_enabled()
```

## Class Dependencies

```
StatusIndicator
├─ Depends on: QWidget, QLabel, QHBoxLayout
├─ Uses colors: ACCENT, MODE_APP, MODE_MEDIA, TEXT_SEC, TEXT_PRI, TEXT_HINT
└─ No external dependencies

ControlPanel
├─ Depends on:
│   ├─ QFrame, QLabel, QSlider, QPushButton, QCheckBox
│   ├─ SharedState (for mode signal)
│   └─ Layout classes (QVBoxLayout, QHBoxLayout)
├─ Uses colors: All theme colors
├─ Emits signals: 5 custom signals
└─ Connects to: SharedState.mode_changed

SystemPanel Enhancements
├─ Creates:
│   ├─ StatusIndicator (×3)
│   └─ ControlPanel (×1)
├─ Connects slots to:
│   ├─ StatusIndicator (via state signals)
│   └─ ControlPanel (user interactions)
└─ No new external dependencies
```

## Widget Inclusion Chain

```
MainWindow
  └─ CentralWidget
      └─ Body Layout
          ├─ Sidebar
          └─ BodyStack (QStackedWidget)
              └─ Index 0: MainView
                  ├─ VisionPanel
                  └─ SystemPanel ◄── ENHANCED
                      ├─ ScrollArea
                      │   └─ Container
                      │       ├─ StatusCard (with ×3 StatusIndicator) ◄── NEW
                      │       ├─ ControlPanel ◄── NEW
                      │       ├─ SystemCard
                      │       ├─ ModeCard
                      │       ├─ GestureGuideCard
                      │       └─ PerformanceCard
```

## Styling Cascade

```
GLOBAL_QSS (applied to MainWindow)
  └─ All colors defined (BG_DEEP, ACCENT, etc.)
  └─ Scroll bars styled
  └─ Buttons/checkboxes base styles

SystemPanel StyleSheet
  └─ background-color: BG_DEEP

StatusCard & ControlPanel StyleSheet (inline)
  └─ background: BG_CARD
  └─ border: 1px BORDER, border-radius: 12px
  └─ All child elements inherit + override

Individual Widget QSS (inline)
  ├─ Slider:
  │   ├─ groove: BORDER, 5px height
  │   └─ handle: MODE_APP/MODE_MEDIA, 14px diameter
  │
  ├─ Button:
  │   ├─ default: rgba(white, 0.05)
  │   ├─ hover: rgba(mode_color, 0.2)
  │   └─ active: rgba(mode_color, 0.4)
  │
  └─ CheckBox:
      ├─ indicator: 14px square
      ├─ unchecked: BORDER background
      └─ checked: MODE_APP/ACTIVE background
```

## Rendering Pipeline

```
User Action (slider movement, button click, etc.)
    ↓
Qt Event Loop
    ↓
QWidget Signal Emission
    ↓
    ├─ _on_* Slot Execution (if connected)
    └─ emit Signal (if custom signal)
    ↓
Connected Slot Execution
    ↓
QLabel/QSlider/QPushButton Update (repaint)
    ↓
Qt Paint Engine (GPU-accelerated on most platforms)
    ↓
Display Update (typically <16ms at 60 FPS)
```

## Memory Layout

```
SystemPanel Instance Memory
├─ Inherited from QWidget (~1KB)
├─ Layout objects (~2KB)
├─ StatusIndicator (×3) (~1.5KB each = 4.5KB)
├─ ControlPanel (~2KB)
├─ Cached signals/connections (~1KB)
├─ QSS stylesheets (cached globally, not counted)
└─ Total per panel: ~10–12KB (negligible)

Application Total Memory Impact: <50KB
```

## Future Extensibility Points

```
StatusIndicator
├─ Add animation (pulse, fade)
├─ Add tooltip with details
├─ Add context menu
└─ Subclass for domain-specific indicators

ControlPanel
├─ Add slider value history/graph
├─ Add preset buttons (quick save/load)
├─ Add calibration wizard integration
├─ Add per-mode sensitivity overrides
└─ Subclass for specialized control panels

SystemPanel
├─ Add more status indicators (FPS, latency, etc.)
├─ Add chart/graph widgets
├─ Add real-time metric display
└─ Add gesture/voice recording/playback tools
```

---

**Diagram Last Updated**: April 7, 2026  
**Version**: 1.0 (Complete)  
**Status**: Ready for Integration ✅
