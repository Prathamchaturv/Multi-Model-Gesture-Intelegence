#!/usr/bin/env python3
"""
Quick test to verify mute action executes correctly.
"""

import sys
sys.path.insert(0, 'd:/Projects/MMGI')

from execution.cursor_control import ActionExecutor

# Create executor
executor = ActionExecutor()

print("\n" + "="*70)
print("TEST: Execute mute action with detailed logging")
print("="*70 + "\n")

# Execute mute action
print("Calling: executor.execute('mute')")
executor.execute('mute')

print("\nTest complete. Check logs above to see execution path.")
print("="*70 + "\n")
