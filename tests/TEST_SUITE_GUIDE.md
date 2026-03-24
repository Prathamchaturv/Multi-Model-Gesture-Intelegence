# MMGI Comprehensive Test Suite Documentation

## Overview

This documentation describes the comprehensive pytest test suite for the MMGI (Multimodal Gesture and Voice Interface) system. The test suite is organized into focused groups, each testing specific aspects of the system.

## Test Suite Organization

### Test Files

1. **test_voice_action_mapping.py** - Voice command recognition and execution
   - Voice command mapping to actions
   - Mode-specific voice mappings
   - Confidence threshold handling
   - Edge cases (unmapped commands, case sensitivity)
   - ~60 test cases

2. **test_multimodal_edge_cases.py** - Multimodal fusion edge cases and stress scenarios
   - Conflicting input signals
   - Timing and synchronization issues
   - Confidence score combinations
   - Sensor failure recovery
   - Mode-specific fusion behavior
   - ~45 test cases

3. **test_performance_stress.py** - Performance and load testing
   - High-frequency input processing (100+ events/sec)
   - Memory management and leak detection
   - Latency under load (<50ms for gestures, <100ms for voice)
   - Throughput measurement
   - Resource exhaustion scenarios
   - ~35 test cases

4. **test_authentication_security.py** - Security and authentication
   - User authentication flows
   - Face recognition security
   - Multi-user scenarios
   - Action authorization and access control
   - Voice authentication
   - Security policy enforcement
   - ~40 test cases

5. **test_e2e_comprehensive.py** - End-to-end workflows and integration
   - Complete user sessions (media control, browsing, system control)
   - Multi-step workflows
   - Cross-module integration
   - Real-world usage patterns
   - Error recovery workflows
   - ~55 test cases

6. **conftest.py** - Shared pytest fixtures and configuration
   - Mock classes for all components
   - Fixture definitions
   - Test markers and configuration
   - ~180 test cases total

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_voice_action_mapping.py

# Run specific test class
pytest tests/test_voice_action_mapping.py::TestVoiceToActionMapping

# Run specific test
pytest tests/test_voice_action_mapping.py::TestVoiceToActionMapping::test_open_brave_command_app_mode

# Run with verbose output
pytest -v tests/

# Run with print statements visible
pytest -s tests/
```

### Test Selection

```bash
# Run only voice tests
pytest -k "voice" tests/

# Run only gesture tests
pytest -k "gesture" tests/

# Run only security tests
pytest -m security tests/

# Run only performance tests (requires --run-performance)
pytest --run-performance tests/test_performance_stress.py

# Run tests that are not slow
pytest -m "not slow" tests/
```

### Coverage

```bash
# Generate coverage report
pytest --cov=engine --cov=core --cov=ui --cov-report=html tests/

# View coverage in browser
open htmlcov/index.html
```

## Test Markers

Mark tests with decorators for organization:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.e2e
def test_end_to_end():
    pass

@pytest.mark.performance
def test_performance():
    pass

@pytest.mark.security
def test_auth():
    pass

@pytest.mark.stress
def test_load():
    pass

@pytest.mark.slow
def test_very_long():
    pass
```

Run by marker:
```bash
pytest -m unit              # Only unit tests
pytest -m "security or performance"  # Multiple markers
pytest -m "not slow"        # Exclude marker
```

## Fixtures

### Core Fixtures (from conftest.py)

- **mmgi_pipeline** - Complete pipeline with: decision_engine, action_executor, face_security, etc.
- **gesture_event** - Factory to create gesture InputEvent
- **voice_input_event** - Factory to create voice InputEvent
- **spy_action_executor** - Mock executor that tracks calls
- **mock_face_security** - Mock face security manager
- **decision_engine** - Mock decision engine
- **gesture_history** - Track gesture events
- **voice_history** - Track voice events
- **test_configs** - Test configuration dict
- **mock_metrics** - Metrics collection mock

### Usage Example

```python
def test_something(mmgi_pipeline, gesture_event, voice_input_event):
    engine = mmgi_pipeline["decision_engine"]
    executor = mmgi_pipeline["action_executor"]
    
    # Create input events
    gesture = gesture_event("palm_open", confidence=0.95)
    voice = voice_input_event("click", mode="App Mode", confidence=0.9)
    
    # Test logic
    outcome = engine.decide(gesture)
    
    # Verify execution
    assert executor.was_called_with("open")
```

## Test Implementation Patterns

### Pattern 1: Basic Action Test

```python
def test_open_youtube_command(self, mmgi_pipeline, voice_input_event):
    engine = mmgi_pipeline["decision_engine"]
    executor = mmgi_pipeline["action_executor"]
    
    event = voice_input_event("open_youtube", mode="App Mode", confidence=0.9)
    outcome = engine.decide(event)
    
    if outcome and outcome.action:
        executor.execute(outcome.action)
    
    assert outcome is not None
    assert outcome.action == "open_youtube"
```

### Pattern 2: Multimodal Fusion Test

```python
def test_conflicting_gesture_voice_commands(self, mmgi_pipeline, gesture_event, voice_input_event):
    engine = mmgi_pipeline["decision_engine"]
    executor = mmgi_pipeline["action_executor"]
    
    gesture_evt = gesture_event("swipe_down", confidence=0.95)
    voice_evt = voice_input_event("open_brave", mode="App Mode", confidence=0.9)
    
    outcome1 = engine.decide(gesture_evt)
    outcome2 = engine.decide(voice_evt)
    
    # Both should be processable
    assert outcome1 is not None or outcome2 is not None
```

### Pattern 3: Performance Test

```python
def test_100_rapid_gestures(self, mmgi_pipeline, gesture_event):
    engine = mmgi_pipeline["decision_engine"]
    executor = mmgi_pipeline["action_executor"]
    
    executor.reset()
    start_time = time.time()
    
    for i in range(100):
        evt = gesture_event("palm_open", confidence=0.95)
        outcome = engine.decide(evt)
        if outcome and outcome.action:
            executor.execute(outcome.action)
    
    elapsed = time.time() - start_time
    throughput = 100 / elapsed if elapsed > 0 else 0
    
    # Should handle 100+ events per second
    assert throughput > 50
```

### Pattern 4: Security Test

```python
def test_unauthenticated_user_no_actions(self, mmgi_pipeline, gesture_event):
    engine = mmgi_pipeline["decision_engine"]
    executor = mmgi_pipeline["action_executor"]
    
    executor.reset()
    
    evt = gesture_event("palm_open", confidence=0.95)
    outcome = engine.decide(evt)
    
    if outcome and outcome.action:
        executor.execute(outcome.action)
    
    # Without auth, execution should be prevented
    assert executor.call_count() == 0
```

## Test Data and Configurations

### Gesture Commands

- `palm_open` - Open palm hand
- `fist_closed` - Closed fist
- `swipe_left` - Swipe left motion
- `swipe_right` - Swipe right motion
- `swipe_up` - Swipe up motion
- `swipe_down` - Swipe down motion
- `point_and_click` - Point and click gesture
- `peace_sign` - Peace sign hand
- `pinch_in` - Pinch inward
- `pinch_out` - Pinch outward

### Voice Commands

- `open_brave` - Open Brave browser
- `open_youtube` - Open YouTube
- `close_window` - Close active window
- `switch_tab` - Switch browser tabs
- `play_song` - Play song/media
- `next_track` - Next track
- `volume_up` - Increase volume
- `volume_down` - Decrease volume
- `mute` - Mute audio
- `lock_screen` - Lock screen

### Operation Modes

- `App Mode` - Application control
- `Media Mode` - Media playback control
- `System Mode` - System-level control

## Mock Components

### SpyActionExecutor

Tracks action calls without executing:

```python
executor = spy_action_executor
executor.execute("open_youtube")
assert executor.was_called_with("open_youtube")
assert executor.call_count("open_youtube") == 1
executor.reset()  # Clear history
```

### MockFaceSecurityManager

Configurable face recognition:

```python
face_security = mock_face_security
face_security.set_authorization(authorized=True, detected=True)
result = face_security.evaluate()
assert result["is_authorized"] is True
```

## Performance Targets

The performance tests validate these targets:

| Metric | Target | Test |
|--------|--------|------|
| Gesture recognition latency | <50ms avg, <200ms max | test_gesture_recognition_latency |
| Voice recognition latency | <100ms avg, <300ms max | test_voice_recognition_latency |
| Action execution latency | <20ms avg | test_action_execution_latency |
| End-to-end latency | <100ms avg, <300ms max | test_end_to_end_latency |
| Gesture throughput | ≥100/sec | test_gestures_per_second |
| Mixed input throughput | ≥50/sec | test_mixed_inputs_per_second |
| Memory increase (1000 events) | <100 MB | test_memory_after_1000_events |

## Common Issues and Debugging

### Issue: Tests timeout

**Solution:** Use `--timeout=300` flag or increase timeout in conftest.py

```bash
pytest --timeout=300 tests/
```

### Issue: Memory tests fail

**Solution:** Run alone to avoid interference:

```bash
pytest tests/test_performance_stress.py::TestMemoryManagement -v
```

### Issue: Mock returns None

**Solution:** Check InputEvent initialization:

```python
event = InputEvent(
    type="gesture",      # Required
    command="palm_open", # Required
    confidence=0.95,     # Required
    timestamp=None,      # Can be None
    mode="App Mode",     # Required for tests
)
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov
```

### Run Different Test Suites

```bash
# Unit tests only (fast)
pytest -m unit -v

# Integration tests (medium)
pytest -m integration -v

# E2E tests (slower)
pytest -m e2e -v

# All tests with coverage
pytest tests/ --cov --cov-report=html

# Performance tests (requires flag)
pytest --run-performance tests/test_performance_stress.py

# Security tests
pytest -m security -v
```

## Adding New Tests

### New Test File Template

```python
"""
test_new_feature.py - Tests for new feature.

Tests:
- Feature behavior A
- Feature behavior B
"""

import pytest


class TestNewFeature:
    """Test new feature functionality."""
    
    def test_basic_behavior(self, mmgi_pipeline, gesture_event):
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Test implementation
        
        assert True


class TestNewFeatureEdgeCases:
    """Test edge cases."""
    
    def test_edge_case(self, mmgi_pipeline):
        # Test implementation
        assert True
```

### Adding to conftest.py

```python
@pytest.fixture
def new_mock():
    """Provide new mock."""
    mock = Mock()
    mock.some_method = Mock(return_value="result")
    return mock
```

## Best Practices

1. **One assertion per behavior** - Each test should verify one thing
2. **Clear test names** - Use `test_<feature>_<scenario>_<expected_result>` pattern
3. **Use fixtures** - Don't create mocks in tests, use fixtures
4. **Reset state** - Use `executor.reset()`, etc. between tests
5. **Arrange-Act-Assert** - Structure tests clearly
6. **Avoid sleeps** - Use mocks instead of real timing
7. **Test both paths** - Success and failure cases
8. **Document non-obvious tests** - Add docstrings explaining purpose

## Continuous Testing

Run tests locally before committing:

```bash
# All tests
pytest tests/ -v

# Fast check (unit + basic integration)
pytest -m "not performance and not slow" -v

# Full validation (all tests)
pytest tests/ --cov --run-performance -v
```

## Performance Benchmarking

To establish performance baselines:

```bash
pytest tests/test_performance_stress.py -v --benchmark

# Compare with previous run
pytest tests/test_performance_stress.py -v --benchmark --compare=previous
```

## Troubleshooting Test Failures

1. **Check mock setup** - Ensure fixtures are initialized properly
2. **Verify event types** - InputEvent requires type, command, confidence
3. **Check mode context** - Some tests need specific modes
4. **Review confidence thresholds** - Low confidence events may be rejected
5. **Check state** - Mocks may retain state between tests
6. **Run single test** - Isolate failures with `-k` or `::`

## Support

For issues or new test scenarios:
1. Check existing test patterns in the appropriate test file
2. Review conftest.py for available fixtures
3. Add test case following existing patterns
4. Ensure all assertions are clear and specific
5. Run with `-v` and `-s` flags for debugging
