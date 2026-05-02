#!/usr/bin/env python3
"""
Debug script to trace voice command routing through decision engine.
Tests if "mute" command resolves to "mute" action in Media Mode.
"""

import sys
sys.path.insert(0, 'd:/Projects/MMGI')

from engine.decision_engine import DecisionEngine, InputEvent
from core.config_manager import ConfigManager

# Initialize decision engine with config manager
config_mgr = ConfigManager()
decision_engine = DecisionEngine(config_manager=config_mgr)

# Set to Media Mode
decision_engine.current_mode = 'Media Mode'
print(f"[TEST] Current mode: {decision_engine.current_mode}")

# Test voice commands
test_commands = [
    'mute',
    'volume_up',
    'volume_down',
    'next_track',
    'play_pause',
    'open_youtube',
]

print("\n[TEST] Testing voice command resolution in Media Mode:")
print("-" * 70)

for command in test_commands:
    # Create a voice input event
    voice_event = InputEvent(
        type='voice',
        command=command,
        confidence=0.9,
        timestamp=None,
    )
    
    # Get decision from decision engine
    decision = decision_engine.decide(voice_event, mode='Media Mode')
    
    action_str = str(decision.action) if decision.action else 'NONE'
    reason_str = str(decision.reason) if decision.reason else 'OK'
    print(f"Command: {command:20} => Action: {action_str:20} (Reason: {reason_str})")

print("-" * 70)

# Debug: Check the actual voice action maps loaded
print("\n[DEBUG] Voice action maps per mode:")
for mode, mappings in decision_engine._voice_action_maps.items():
    print(f"\n  {mode}:")
    for cmd, action in sorted(mappings.items()):
        print(f"    {cmd:20} => {action}")

print("\n[DEBUG] Action whitelist per mode:")
for mode, actions in decision_engine._action_whitelist.items():
    print(f"  {mode}: {sorted(actions)}")

print("\n[SUCCESS] Diagnostic complete")
