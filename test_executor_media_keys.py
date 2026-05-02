#!/usr/bin/env python3
"""
Test ActionExecutor media key execution.
"""

import sys
sys.path.insert(0, 'd:/Projects/MMGI')

from execution.cursor_control import ActionExecutor

# Create executor
executor = ActionExecutor()
print("[TEST] ActionExecutor instantiated")

# Test media key execution
print("\n[TEST] Testing media key execution:")
print("-" * 60)

test_actions = [
    'volume_up',
    'volume_down',
    'mute',
    'next_track',
    'play_pause',
]

for action in test_actions:
    try:
        print(f"\nExecuting: {action}")
        executor.execute(action)
        print(f"  [OK] Executed {action}")
    except Exception as exc:
        print(f"  [ERROR] {exc}")

print("\n" + "-" * 60)
print("[SUCCESS] Execution test complete")
print("\nIf no errors above, the media keys should have been sent to your system.")
print("Check if system volume changed, or if media player responded.")
