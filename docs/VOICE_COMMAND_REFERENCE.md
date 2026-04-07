# Voice Command Groups Reference

## Quick Lookup Table

All default voice command groups with phrase variations available in MMGI.

| Command ID | Phrases | Category |
|------------|---------|----------|
| **open_brave** | open brave, open brave browser, launch brave, start brave, open browser | App Launch |
| **open_apple_music** | open apple music, open music, launch apple music, start music | App Launch |
| **open_youtube** | open youtube, launch youtube, start youtube | App Launch |
| **close_window** | close window, close this window, close app, exit app, shut window | Window Mgmt |
| **switch_tab** | switch tab, next tab, change tab, move tab | Browser Control |
| **scroll_down** | scroll down, go down, move down, page down | Scrolling |
| **play_song** | play song, play music, play, resume | Media Playback |
| **pause** | pause song, pause music, pause, stop music | Media Control |
| **next_track** | next track, next song, skip, skip track | Track Navigation |
| **previous_track** | previous track, previous song, back track, go back track | Track Navigation |
| **volume_up** | volume up, increase volume, raise volume, louder | Volume Control |
| **volume_down** | volume down, decrease volume, lower volume, softer | Volume Control |
| **mute** | mute, silence, mute audio | Audio Control |

## Adding Custom Commands

Edit `config/voice_control.json` to add or override commands:

```json
{
  "command_groups": {
    "my_custom_action": [
      "phrase one",
      "phrase two",
      "phrase three"
    ]
  }
}
```

### Example: Adding "Take Screenshot"

```json
{
  "command_groups": {
    "take_screenshot": [
      "screenshot",
      "capture screen",
      "take a picture",
      "grab screen"
    ]
  }
}
```

The new command will be immediately available after the file is saved (hot-reload within 0.5s).

## Confidence Scoring Examples

### Exact Matches (Confidence = 1.0)
```
User says: "scroll down"
Mapped to: scroll_down [confidence: 1.0]
```

### Phrase Variations (Confidence = token_overlap / total_tokens)
```
User says: "go down"
Matched against: "scroll down" (2 tokens: "scroll", "down")
Overlap: 1 token ("down")
Confidence: 1/2 = 0.5

User says: "page down"
Matched against: "scroll down" (2 tokens)
Overlap: 1 token ("down")
Confidence: 1/2 = 0.5
```

### No Match (Confidence = 0.0)
```
User says: "xyz unknown phrase"
Mapped to: None [confidence: 0.0]
```

## Filtering Based on Confidence Threshold

Default: `confidence_threshold = 0.6`

### Execution Decision Tree
```
if confidence >= threshold:
    execute_action()
else:
    discard_event()  # Too uncertain
```

### Example with Default Threshold (0.6)
```
Exact match "scroll down" → confidence 1.0 ≥ 0.6 ✓ EXECUTE
Partial match "go down" → confidence 0.5 < 0.6 ✗ DISCARD (too low)
```

## Adjusting Confidence Threshold

For different confidence requirements, edit `config/voice_control.json`:

```json
{
  "confidence_threshold": 0.9  // Very strict (only exact + near-exact)
}
```

| Threshold | Use Case | Effect |
|-----------|----------|--------|
| 0.3 | Relaxed, casual navigation | Accepts most variations, some false positives |
| 0.5 | Moderate, most applications | Balances coverage and accuracy |
| 0.6 | Current default | Recommended for general use |
| 0.8 | Strict, safety-critical | Only high-confidence matches |
| 0.95 | Very strict, sensitive operations | Near-exact matches only |

## Command Group Modes

MMGI uses different action mappings per system mode:

- **App Mode**: `open_brave`, `open_youtube`, `close_window`, `switch_tab`, `scroll_down`
- **Media Mode**: `play_song`, `pause`, `next_track`, `previous_track`, `volume_up`, `volume_down`, `mute`
- **System Mode**: All commands available (gesture control disabled)

Commands unmapped for a mode are silently ignored during execution.

## Testing Your Configuration

After editing `config/voice_control.json`, the new commands are auto-loaded within 0.5 seconds.

To test:
1. Say a phrase from your new command group
2. Check dashboard for recognized command or error message
3. Verify action executed if confident enough

## Related Documentation

- [docs/VOICE_COMMAND_MAPPER.md](VOICE_COMMAND_MAPPER.md) — Full architecture and advanced features
- [core/voice_control.py](../core/voice_control.py) — Source implementation
- [config/voice_control.json](../config/voice_control.json) — Configuration file
- [tests/test_voice_command_mapper.py](../tests/test_voice_command_mapper.py) — Test suite with examples

## Troubleshooting

**Issue**: Command not recognized
- **Check**: Is confidence above threshold? (Check overlay or logs)
- **Fix**: Use exact phrase or re-enunciate more clearly

**Issue**: Wrong command executed
- **Check**: Did voice transcript match an unintended command?
- **Fix**: Refine phrase variations in your custom groups to be more distinct

**Issue**: New commands not loading
- **Check**: Is `command_groups` correctly formatted in JSON?
- **Fix**: Validate JSON syntax (no trailing commas, proper quotes)

**Issue**: All commands stopped working
- **Check**: Is `confidence_threshold` set to 1.0 (too strict)?
- **Fix**: Reset to default `0.6` or appropriate for your use case
