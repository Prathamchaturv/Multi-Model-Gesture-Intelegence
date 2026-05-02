#!/usr/bin/env python3
"""
Test if voice_control.json is being loaded correctly.
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, 'd:/Projects/MMGI')

# Simulate what worker_thread.py does
voice_control_path = Path('d:/Projects/MMGI/config/voice_control.json')

print(f"[TEST] Voice control file path: {voice_control_path}")
print(f"[TEST] File exists: {voice_control_path.exists()}")

if voice_control_path.exists():
    with open(voice_control_path, 'r', encoding='utf-8') as fh:
        config_data = json.load(fh)
    
    print(f"\n[TEST] Config loaded from JSON:")
    print(f"  - enabled: {config_data.get('enabled')}")
    print(f"  - system_mode_only: {config_data.get('system_mode_only')}")
    print(f"  - listen_timeout_s: {config_data.get('listen_timeout_s')}")
    print(f"  - phrase_time_limit_s: {config_data.get('phrase_time_limit_s')}")
    print(f"  - energy_threshold: {config_data.get('energy_threshold')}")
    print(f"  - noise_gate_rms: {config_data.get('noise_gate_rms')}")
    print(f"  - noise_reduction_enabled: {config_data.get('noise_reduction_enabled')}")
    
    # Now test the settings loading logic
    from ui.worker_thread import _load_voice_control_settings
    from core.config_manager import Config
    
    # Create an empty config
    config = Config()
    
    # Load voice control settings
    settings = _load_voice_control_settings(config)
    
    print(f"\n[TEST] Settings returned by _load_voice_control_settings():")
    print(f"  - enabled: {settings.get('enabled')}")
    print(f"  - system_mode_only: {settings.get('system_mode_only')}")
    print(f"  - listen_timeout_s: {settings.get('listen_timeout_s')}")
    print(f"  - phrase_time_limit_s: {settings.get('phrase_time_limit_s')}")
    print(f"  - energy_threshold: {settings.get('energy_threshold')}")
    print(f"  - noise_gate_rms: {settings.get('noise_gate_rms')}")
    print(f"  - noise_reduction_enabled: {settings.get('noise_reduction_enabled')}")
    
    if settings.get('system_mode_only') == False:
        print("\n[SUCCESS] system_mode_only is correctly set to False")
        print("  Voice commands should work in all modes!")
    else:
        print(f"\n[ERROR] system_mode_only is {settings.get('system_mode_only')}, should be False!")
        print("  This explains why voice commands only work in System Mode!")
