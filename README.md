# Multi-Model Gesture Intelligence System

A real-time multimodal human-computer interaction platform that combines gesture recognition, voice commands, and face-based authorization to control desktop actions in a secure and adaptive way.

Built for practical deployment and academic evaluation, this project demonstrates how computer vision, speech interfaces, and runtime policy control can be integrated into one robust system.

## Introduction

The Multi-Model Gesture Intelligence System is designed to reduce friction between users and machines by enabling touchless, context-aware interaction.

Instead of relying on a single input modality, the system fuses:
- Hand gestures for intuitive motion control
- Voice commands for natural language interaction
- Face verification for secure execution

This multimodal approach improves reliability, usability, and safety in dynamic real-world conditions.

## Key Features

### Gesture Intelligence
- Real-time hand tracking and gesture classification
- Mode-aware gesture-to-action mapping
- Activation and cooldown safeguards to avoid accidental triggers
- Stable detection pipeline with confidence-based filtering

### Voice Command Interface
- Live microphone listening pipeline
- Speech-to-command normalization and mapping
- In-dashboard voice controls with live status and command feedback
- Voice-assisted action triggering through the unified decision flow

### Face Security and Authorization
- Face-based authorization gate for sensitive actions
- Authorized vs unknown user discrimination
- Runtime lock/pause behavior when identity confidence is low
- Security-first action blocking under unsafe identity conditions

## Context-Aware System

The platform resolves the same gesture differently based on active context.

Examples:
- In browser context, swipe can map to scrolling behavior
- In media context, swipe can map to seek or volume actions
- In system context, swipe can map to app-switch workflows

Context awareness makes controls feel natural for real usage rather than fixed one-gesture-one-action logic.

## Tech Stack

### Core Runtime
- Python 3.10+
- OpenCV
- MediaPipe
- NumPy

### Voice and Audio
- SpeechRecognition
- sounddevice

### UI and Interaction
- PyQt6

### System Automation and Security
- PyAutoGUI
- pywin32
- psutil
- bcrypt

### Testing
- pytest

## How to Run

### Prerequisites
- Windows 10/11 recommended
- Python 3.10+
- Webcam
- Microphone (for voice features)

### Installation
1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Run Dashboard Mode
```bash
python main.py
```

### Run Headless Mode
```bash
python main.py --no-ui
```

### Optional Legacy Alias
```bash
python main.py --headless
```

## Screenshots and Demo Placeholders

Add your evaluation media here:
- UI Dashboard Screenshot: assets/ui_screenshot.png
- Runtime Demo GIF: assets/demo.gif
- System Workflow Diagram: assets/workflow.png
- Architecture Diagram: assets/architecture.png

Suggested documentation captions:
- Live multimodal dashboard with runtime telemetry
- Gesture and voice command execution timeline
- Face security lock/unlock states
- Context-aware decision routing flow

## Future Scope

- Multi-face identification with prioritized authorization roles
- Adaptive personalization of gesture and voice profiles per user
- Cross-platform action execution adapters
- Enhanced continuous learning for user-specific gesture variance
- Cloud-assisted analytics and session-level behavior reporting
- Expanded multilingual voice command support
- Mobile and edge deployment variants

## Evaluation Highlights

- Modular architecture with clear separation of core logic, orchestration, and UI
- Safety-first execution strategy with confidence and authorization guards
- Reusable multimodal pipeline suitable for research and product prototyping
- Strong extensibility for future AI-assisted interaction capabilities

---

If you are evaluating this project, focus on the combined strengths of multimodal fusion, context-aware action resolution, and secure runtime control under real-time constraints.
