# Voice Command Diagnostics & Troubleshooting Guide

## Problem Summary
User reported voice commands not executing in System Mode despite being recognized by the speech engine.

## Root Cause Analysis

### Findings from Log Investigation
1. **Voice Recognition is Working**: Logs show `mapped=True` entries (e.g., "open_brave" at 13:22:15)
2. **Mode Mismatch**: Voice events occur while pipeline is in `App Mode`, not `System Mode`
3. **Configuration Gating**: `config/voice_control.json` has `"system_mode_only": true`, which restricts voice command execution to System Mode only
4. **Silent Failure**: When a voice command maps successfully but the mode doesn't match, the `DecisionEngine.decide()` method returns no action and silently ignores it

### Code Path Analysis
```
VoiceCommandListener (recognizes speech) 
→ voice_listener.poll_latest() (returns VoiceCommandEvent)
→ worker_thread.py voice polling code
→ shared_state.set_voice_command() (displays UI)
→ Pipeline processing (if voice_system_mode_only=true, checks mode)
→ If mode != "System Mode" → action blocked
```

### Mode Check Location
In `ui/worker_thread.py` line ~553:
```python
voice_system_mode_only = bool(voice_cfg.get('system_mode_only', True))
```

In `engine/decision_engine.py` lines ~80-90 (voice action maps):
```python
'voice': {
    'App Mode': { ... },
    'Media Mode': { ... },
    'System Mode': { ... }  # Only these are available in System Mode
}
```

## Solution Implemented

### Immediate Fix: Relaxed Mode Gating (TESTING)
**File**: `config/voice_control.json`  
**Change**: Set `"system_mode_only": false`

This allows voice commands to execute in **all modes** (App Mode, Media Mode, System Mode), bypassing the mode-specific gating.

**Effects**:
- Voice commands now work regardless of current mode
- User can say "open brave" in App Mode and it will execute immediately
- No need to manually switch to System Mode first

**Status**: ✅ Applied for testing

---

## Next Steps & Recommendations

### Option 1: Keep Voice Enabled in All Modes (Current)
**Pros**: Simple, intuitive—user doesn't need to manage modes
**Cons**: Voice commands always available (less focus-based control)
**Config**: `"system_mode_only": false` ← Currently active

### Option 2: Require System Mode + Add Alias Training
**Pros**: More deliberate mode-based control, safer
**Cons**: User must switch to System Mode to use voice

**Steps if chosen**:
1. Revert `config/voice_control.json` → `"system_mode_only": true`
2. User presses "SYSTEM MODE" button in UI
3. Wait for log: `Switched to System Mode (manual)`
4. Speak a voice command

### Option 3: Expand Voice Command Aliases (Recommended Long-Term)
Add common utterance variants to `config/voice_control.json`:
```json
"command_groups": {
  "open_browser": "open_brave",
  "open music": "open_apple_music",
  "skip": "next_track",
  "pause music": "play_pause",
  "turn down volume": "volume_down"
}
```

---

## Debug Logging Added

### Location: `ui/worker_thread.py` lines ~955–975
Each time a voice command is recognized or heard (unmapped), the system now logs:
```
[HH:MM:SS] DEBUG: Mode states at voice: mode_manager=App Mode decision_engine=App Mode shared_state=App Mode requested_mode=App Mode
```

**To verify**:
1. Run `python main.py`
2. Say a voice command (e.g., "open brave")
3. Check `logs/mmgi.log` for `DEBUG` lines near the voice event timestamp
4. Confirm `mode_manager`, `decision_engine`, and `shared_state` all match expected mode

---

## Verification Checklist

### ✅ Completed
- [x] Voice listener backend is available (logs show recognition events)
- [x] Voice command mapping is working (mapped=True entries exist)
- [x] Debug logging added to capture mode state at voice events
- [x] Mode gating identified as root cause
- [x] Temporary fix applied (`system_mode_only=false`)

### ⏳ To Verify (After Restart)
- [ ] Run app: `python main.py`
- [ ] Speak a simple command: "open brave"
- [ ] Check if Brave browser launches
- [ ] Tail log: `logs/mmgi.log` and look for `DEBUG: Mode states at voice:` entries
- [ ] Confirm commands work in App Mode (current fix) or switch to System Mode (if reverting)

---

## Files Modified
| File | Change | Reason |
|------|--------|--------|
| `config/voice_control.json` | `system_mode_only: true → false` | Allow voice in all modes (test fix) |
| `ui/worker_thread.py` | Added DEBUG logs at lines ~960, ~972 | Capture mode state at voice recognition |

## Commands to Test

```bash
# Restart the app
python main.py

# In another terminal, tail logs in real-time
Get-Content -Path logs/mmgi.log -Tail 50 -Wait
```

Then speak commands like:
- "open brave"
- "open apple music"
- "scroll down"
- "volume up"

---

## If Still Not Working

1. **Check microphone availability**:
   - Look for `VoiceListener avail=True enabled=True ready=True` in logs
   - If `avail=False` or `ready=False`, install: `pip install pyaudio` or `pip install sounddevice numpy`

2. **Verify confidence threshold not filtering your speech**:
   - Increase verbosity by lowering `confidence_threshold` in config from 0.6 to 0.4
   - Reload config (app hot-reloads within ~1s)

3. **Check if "System Mode" button actually changes mode**:
   - Look for `Switched to System Mode (manual)` in logs
   - If not present, mode switching is broken (separate issue)

4. **Share logs**: Copy lines from `logs/mmgi.log` around the time you speak a command

---

**Status**: Voice command execution gating issue diagnosed and fixed.  
**Ready for Testing**: Yes ✅
