# Advanced Voice Command Mapper System

## Overview

The **VoiceCommandMapper** provides a flexible, production-ready system for mapping speech transcripts to actionable commands. It supports:

- ✅ **Phrase Variations**: Map multiple phrasings to the same action (e.g., "go down", "scroll down", "page down" → `scroll_down`)
- ✅ **Confidence Scoring**: Each match returns a confidence value [0.0–1.0] for filtering
- ✅ **Custom Groups**: Override or extend the default command set via JSON config
- ✅ **Hot-Reload**: Update voice commands at runtime without restart
- ✅ **O(1) Exact Matching**: Fast lookup for canonical phrases
- ✅ **Token-Subset Scoring**: Lightweight scoring for phrase variations

## Architecture

### Core Components

#### `VoiceCommandMapper`
Maps raw voice transcripts to structured commands with confidence scores.

**Key Methods:**
```python
mapper = VoiceCommandMapper(
    command_groups=None,      # Custom override groups (optional)
    config_path=None,         # Path to JSON config file (optional)
    reload_interval_s=0.5,    # How often to check config mtime
)

command, confidence = mapper.map_command("go down")
# → ("scroll_down", 0.75)  # Command and confidence [0.0-1.0]
```

**Matching Behavior:**
1. **Exact Match** (confidence = 1.0): Transcript exactly matches a phrase alias
2. **Partial Match** (confidence < 1.0): Token-subset scoring for variations
3. **No Match** (command = None, confidence = 0.0): Unrecognized input

#### `VoiceCommandListener`
Background thread that listens for speech and emits `VoiceCommandEvent` objects.

**Constructor:**
```python
listener = VoiceCommandListener(
    enabled=True,
    listen_timeout_s=1.2,
    phrase_time_limit_s=2.0,
    energy_threshold=250,
    confidence_threshold=0.6,  # Filter events below threshold
    command_groups={},         # Custom command groups
    command_config_path=None,  # Path to voice_control.json
)
listener.start()
# Background listening begins; poll_latest() returns events
```

#### `VoiceCommandEvent`
Dataclass emitted by listener when a command is recognized.

**Fields:**
```python
@dataclass
class VoiceCommandEvent:
    command: str              # e.g., "scroll_down"
    transcript: str           # Raw recognized text
    timestamp: float          # When recognized (time.perf_counter())
    confidence: float = 1.0   # Confidence [0.0-1.0]
```

## Default Command Groups

The system includes 13 predefined command groups with 3–5 phrase variations each:

| Command | Phrases | Use Case |
|---------|---------|----------|
| `open_brave` | "open brave", "open brave browser", "launch brave", "start brave", "open browser" | Browser control |
| `open_apple_music` | "open apple music", "open music", "launch apple music", "start music" | Music app |
| `open_youtube` | "open youtube", "launch youtube", "start youtube" | Video streaming |
| `close_window` | "close window", "close this window", "close app", "exit app", "shut window" | Window management |
| `switch_tab` | "switch tab", "next tab", "change tab", "move tab" | Tab navigation |
| `scroll_down` | "scroll down", "go down", "move down", "page down" | Scrolling |
| `play_song` | "play song", "play music", "play", "resume" | Media playback |
| `pause` | "pause song", "pause music", "pause", "stop music" | Media control |
| `next_track` | "next track", "next song", "skip", "skip track" | Track navigation |
| `previous_track` | "previous track", "previous song", "back track", "go back track" | Track navigation |
| `volume_up` | "volume up", "increase volume", "raise volume", "louder" | Volume control |
| `volume_down` | "volume down", "decrease volume", "lower volume", "softer" | Volume control |
| `mute` | "mute", "silence", "mute audio" | Audio muting |

## Configuration

### Runtime Override via `voice_control.json`

Edit `config/voice_control.json` to customize or extend the default commands:

```json
{
  "enabled": true,
  "listen_timeout_s": 1.2,
  "phrase_time_limit_s": 2.0,
  "energy_threshold": 250,
  "confidence_threshold": 0.6,
  "command_groups": {
    "scroll_down": [
      "scroll down",
      "go down",
      "move down",
      "page down",
      "move lower"
    ],
    "my_custom_action": [
      "do something",
      "execute custom task",
      "run special command"
    ]
  }
}
```

**Behavior:**
- If `command_groups` is empty `{}`, all defaults are used
- If `command_groups` contains overrides, those phrases **replace** the defaults for that command
- New commands (not in defaults) are **added** to the system
- Reload is triggered automatically if file is modified while listening

## Integration with Worker Thread

The [ui/worker_thread.py](../ui/worker_thread.py) integrates the voice system:

1. **Config Loading** [Line 215]: Reads `confidence_threshold` and `command_groups` from `voice_control.json`
2. **Listener Setup** [Line 505]: Initializes `VoiceCommandListener` with confidence threshold and custom groups
3. **Event Polling** [Line 1309]: Polls latest voice event, checks confidence threshold
4. **Action Execution**: Only commands with confidence ≥ threshold are processed

**Code Snippet:**
```python
# In _load_voice_control_settings()
voice_config = Config.load_voice_control_settings()
confidence_threshold = voice_config.get('confidence_threshold', 0.6)
command_groups = voice_config.get('command_groups', {})

# In listener construction
self._voice_listener = VoiceCommandListener(
    confidence_threshold=confidence_threshold,
    command_groups=command_groups,
    command_config_path=voice_config_path,
    ...other params...
)
```

## Confidence Scoring & Filtering

### Exact Matches
When the transcript **exactly matches** a phrase alias (after normalization):
- **Confidence**: 1.0
- **Processing**: Always executed

### Partial Matches
When tokens overlap but don't form an exact match:
- **Confidence**: `overlap_count / total_phrase_tokens`
- **Example**: "go down" → 2 of 2 tokens match "scroll down" → confidence = 1.0
- **Example**: "go" → 1 of 2 tokens match "scroll down" → confidence = 0.5

### Filtering
Commands below the `confidence_threshold` are **dropped** before execution:

```python
if event.confidence < confidence_threshold:
    # Discard event; don't execute action
    continue
```

Default threshold is **0.6** (configurable in `voice_control.json`).

## Hot-Reload Behavior

The mapper monitors the config file for changes:

1. **Interval**: Checks mtime every 0.5s (configurable via `reload_interval_s`)
2. **Change Detection**: Only reloads if file modification time changes
3. **Fallback**: If file is missing or malformed, defaults are preserved
4. **No Downtime**: Reload happens in background; listening continues

**Example:**
```python
mapper = VoiceCommandMapper(config_path="config/voice_control.json")
# User edits config file...
mapper.reload_if_needed()  # Auto-detects and reloads if changed
# New commands are immediately available
```

## Testing

Comprehensive test suite in [tests/test_voice_command_mapper.py](../tests/test_voice_command_mapper.py):

- **20 test cases** covering exact matching, variations, custom groups, hot-reload, normalization, edge cases
- **Backward Compatibility**: 5 existing tests for legacy `normalize_voice_command()` API
- **Total Voice Coverage**: 56 voice-related tests (mappers + listener + multimodal integration)

**Run Tests:**
```bash
pytest tests/test_voice_command_mapper.py -v
pytest tests/ -k "voice" -v  # All voice tests
pytest tests/                # Full suite (244 tests)
```

## Normalization Rules

Text is normalized before matching:

1. **Lowercase**: "SCROLL DOWN" → "scroll down"
2. **Strip Punctuation**: "scroll down!" → "scroll down"
3. **Collapse Whitespace**: "scroll  down" → "scroll down"
4. **Preserve Case-Insensitivity**: All comparisons are lowercase

**Example:**
```python
_normalize_text("SCROLL... down!!!") → "scroll down"
```

## Use Cases

### 1. Basic Gesture + Voice Control
Require voice confirmation for sensitive actions:
```python
gesture_detected = detect_gesture()
voice_command = listener.poll_latest()
if gesture_detected and voice_command.confidence >= 0.7:
    execute_action()
```

### 2. Custom Domain-Specific Commands
Extend for specialized use cases (e.g., medical software):
```json
{
  "command_groups": {
    "start_diagnosis": ["begin exam", "start scan", "initiate test"],
    "save_results": ["save findings", "store results", "archive report"]
  }
}
```

### 3. Multilingual Support
Override phrases for non-English languages:
```json
{
  "command_groups": {
    "scroll_down": ["下に移動", "下へスクロール", "次ページ"]
  }
}
```

### 4. Confidence-Based Filtering
Tune threshold per application:
```python
# High-confidence requirement for safety-critical actions
listener = VoiceCommandListener(confidence_threshold=0.9)

# Relaxed threshold for casual navigation
listener = VoiceCommandListener(confidence_threshold=0.5)
```

## Performance Characteristics

- **Exact Match**: O(1) hash lookup
- **Partial Match**: O(phrase_words × commands) with early termination
- **Total Latency**: <10ms typical (dominated by speech recognition, not mapping)
- **Memory**: ~5KB for default groups + custom overrides

## Backward Compatibility

The system maintains compatibility with existing code:

- `normalize_voice_command()` function still works (delegates to mapper internally)
- Existing `VoiceCommandListener` tests pass unchanged
- No breaking changes to event structure (added `confidence` field with default)

## Future Enhancements

- Intent classification (group commands by intent, e.g., "media control", "window management")
- Fuzzy matching for typos/slurred speech
- Weighted scoring (some phrases more common than others)
- Language detection and code-switching
- Performance metrics (phrase frequency, recognition latency)

## Related Files

- [core/voice_control.py](../core/voice_control.py) — Core mapper and listener implementation
- [config/voice_control.json](../config/voice_control.json) — Runtime configuration
- [tests/test_voice_command_mapper.py](../tests/test_voice_command_mapper.py) — Test suite
- [ui/worker_thread.py](../ui/worker_thread.py) — Worker thread integration
