#!/usr/bin/env python3
"""Quick test to verify voice listener backend is working."""
import sys
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import speech_recognition as sr
    print("✅ speech_recognition imported successfully")
except ImportError as e:
    print(f"❌ Failed to import speech_recognition: {e}")
    sys.exit(1)

try:
    import sounddevice
    print("✅ sounddevice imported successfully")
except ImportError as e:
    print(f"❌ Failed to import sounddevice: {e}")
    sys.exit(1)

try:
    import numpy
    print("✅ numpy imported successfully")
except ImportError as e:
    print(f"❌ Failed to import numpy: {e}")
    sys.exit(1)

# Test VoiceCommandListener initialization
try:
    from core.voice_control import VoiceCommandListener
    print("✅ VoiceCommandListener imported successfully")
    
    listener = VoiceCommandListener(
        enabled=True,
        listen_timeout_s=1.2,
        phrase_time_limit_s=2.0,
        energy_threshold=250,
        recognition_language='en-IN',
        confidence_threshold=0.6,
    )
    print(f"✅ VoiceCommandListener initialized: is_enabled={listener.is_enabled}")
    
    # Start the listener
    listener.start()
    print("✅ VoiceCommandListener started")
    time.sleep(1)
    
    # Check if ready
    if listener.is_ready:
        print("✅ VoiceCommandListener is READY to listen")
    else:
        print(f"⚠️  VoiceCommandListener not ready yet. Last error: {listener.last_error}")
    
    # Try polling once
    event = listener.poll_latest()
    if event is None:
        print("✅ poll_latest() returned None (expected - no speech input)")
    else:
        print(f"⏺️  poll_latest() returned: {event}")
    
    listener.stop()
    print("✅ VoiceCommandListener stopped cleanly")
    
    print("\n" + "="*60)
    print("✅ VOICE BACKEND TEST PASSED - Ready to run MMGI")
    print("="*60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
