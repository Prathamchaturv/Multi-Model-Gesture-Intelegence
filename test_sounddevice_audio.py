#!/usr/bin/env python3
"""Test sounddevice audio recording directly."""
import sys
import numpy as np
import sounddevice as sd
import time

print("="*70)
print("SOUNDDEVICE AUDIO CAPTURE TEST")
print("="*70)

# List devices
print("\n[1] Available audio devices:")
devices = sd.query_devices()
for i, dev in enumerate(devices):
    if dev.get('max_input_channels', 0) > 0:
        print(f"  Device {i}: {dev['name']} (input channels: {dev['max_input_channels']})")

default_input, _ = sd.default.device
print(f"\nDefault input device: {default_input}")

# Get device info
try:
    device_info = sd.query_devices(default_input, 'input')
    print(f"Device info: {device_info}")
    sample_rate = int(device_info.get('default_samplerate') or 16000)
    print(f"Sample rate: {sample_rate}")
except Exception as e:
    print(f"Error getting device info: {e}")
    sys.exit(1)

# Try to record
print("\n[2] Attempting to record 2 seconds of audio...")
print("   Speak now!")

try:
    duration_s = 2
    frames = int(duration_s * sample_rate)
    
    recording = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=1,
        dtype='int16',
        device=default_input,
        blocking=True,
    )
    
    print(f"\n[3] Recording complete!")
    print(f"   Type: {type(recording)}")
    print(f"   Shape: {getattr(recording, 'shape', 'N/A')}")
    print(f"   Size: {getattr(recording, 'size', 'N/A')}")
    print(f"   Dtype: {getattr(recording, 'dtype', 'N/A')}")
    
    if recording is not None and recording.size > 0:
        # Calculate RMS (root mean square) to check if audio was captured
        rms = np.sqrt(np.mean(recording**2))
        print(f"   RMS (audio level): {rms:.2f}")
        
        if rms > 100:
            print(f"\n✅ AUDIO CAPTURED SUCCESSFULLY (RMS={rms:.2f})")
        else:
            print(f"\n⚠️  Very low audio level (RMS={rms:.2f}) - microphone may not be working")
    else:
        print(f"\n❌ NO AUDIO DATA (recording is None or empty)")
        
except Exception as e:
    print(f"\n❌ Recording failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("="*70)
