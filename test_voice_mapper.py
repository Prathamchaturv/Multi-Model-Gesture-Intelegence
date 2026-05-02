#!/usr/bin/env python3
"""
Test voice command recognition mapping.
"""

import sys
sys.path.insert(0, 'd:/Projects/MMGI')

from core.voice_control import VoiceCommandMapper

# Create mapper with default groups
mapper = VoiceCommandMapper()

# Test various phrases to see what they map to
test_phrases = [
    "mute",
    "volume up",
    "volume down",
    "next track",
    "previous track",
    "play",
    "pause",
    "play song",
    "open youtube",
    "open brave",
    "increase volume",
    "decrease volume",
    "louder",
    "softer",
    "silence",
    "skip",
]

print("[TEST] Voice command mapper phrase recognition:")
print("-" * 70)
for phrase in test_phrases:
    command, confidence = mapper.map_command(phrase)
    print(f"Phrase: '{phrase:25}' => Command: {str(command):20} (conf: {confidence:.2f})")
print("-" * 70)
