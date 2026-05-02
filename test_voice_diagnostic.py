#!/usr/bin/env python3
"""Comprehensive voice system diagnostics."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("MMGI VOICE SYSTEM DIAGNOSTICS")
print("=" * 70)

# Step 1: Check dependencies
print("\n[1] Checking Python dependencies...")
try:
    import speech_recognition as sr
    import sounddevice as sd
    import numpy as np
    print(f"  ✅ speech_recognition: {sr.__version__}")
    print(f"  ✅ sounddevice: {sd.__version__}")
    print(f"  ✅ numpy: {np.__version__}")
except ImportError as e:
    print(f"  ❌ Missing dependency: {e}")
    sys.exit(1)

# Step 2: Check audio devices
print("\n[2] Checking audio devices...")
try:
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    print(f"  ✅ Audio devices found: {len(devices)} total")
    print(f"  ✅ Default input device: {default_input}")
    if isinstance(devices, list):
        for i, dev in enumerate(devices[:5]):
            print(f"     Device {i}: {dev['name']} (channels: {dev['max_input_channels']})")
except Exception as e:
    print(f"  ❌ Audio device error: {e}")
    sys.exit(1)

# Step 3: Test speech recognition backend
print("\n[3] Testing speech recognition backend...")
try:
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 250
    print("  ✅ Recognizer created")
    
    # Try microphone
    try:
        with sr.Microphone() as source:
            print("  ✅ Microphone access OK")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            print("  ✅ Ambient noise calibration OK")
    except Exception as e:
        print(f"  ⚠️  Microphone error (expected if mic in use): {e}")
except Exception as e:
    print(f"  ❌ Speech recognition backend error: {e}")
    sys.exit(1)

# Step 4: Test VoiceCommandListener
print("\n[4] Testing VoiceCommandListener...")
try:
    from core.voice_control import VoiceCommandListener, VoiceCommandMapper
    
    mapper = VoiceCommandMapper()
    mapped_cmd, score = mapper.map_command("open brave")
    print(f"  ✅ Command mapper working: 'open brave' -> {mapped_cmd} (score: {score})")
    
    listener = VoiceCommandListener(
        enabled=True,
        listen_timeout_s=1.2,
        phrase_time_limit_s=2.0,
    )
    print(f"  ✅ VoiceCommandListener created")
    print(f"  Status: enabled={listener.is_enabled}, ready={listener.is_ready}")
    
    listener.start()
    time.sleep(1)
    print(f"  ✅ VoiceCommandListener started")
    print(f"  Status after start: enabled={listener.is_enabled}, ready={listener.is_ready}")
    
    # Try polling (should be None without actual speech)
    event = listener.poll_latest()
    print(f"  ✅ poll_latest() call OK: event={event}")
    
    listener.stop()
    print(f"  ✅ VoiceCommandListener stopped")
    
except Exception as e:
    print(f"  ❌ VoiceCommandListener error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test configuration
print("\n[5] Checking configuration...")
try:
    import json
    config_path = Path(__file__).parent / "config" / "voice_control.json"
    
    with open(config_path) as f:
        config = json.load(f)
    
    print(f"  ✅ Config file loaded: {config_path}")
    print(f"  - enabled: {config.get('enabled', 'N/A')}")
    print(f"  - system_mode_only: {config.get('system_mode_only', 'N/A')}")
    print(f"  - confidence_threshold: {config.get('confidence_threshold', 'N/A')}")
    print(f"  - command_groups: {len(config.get('command_groups', {}))} custom groups")
    print(f"  - system_mode_voice_actions: {len(config.get('system_mode_voice_actions', {}))} actions")
    
except Exception as e:
    print(f"  ❌ Config error: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL VOICE SYSTEM CHECKS PASSED")
print("=" * 70)
print("\nTo test voice command recognition:")
print("  1. Start the app: python main.py")
print("  2. Speak a command: 'open brave', 'volume up', etc.")
print("  3. Watch logs for [VOICE-0] and [ACTION] entries")
print("  4. Command should execute if recognized and validated")
print("=" * 70)
