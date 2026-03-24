"""
conftest.py - Shared pytest fixtures and mocking utilities for MMGI integration tests.

Provides:
- Mock camera, hand tracker, gesture classifier
- Mock voice listener
- Mock ActionExecutor with call tracking
- Mock face security manager
- Fixture-based pipeline setup
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from engine.decision_engine import DecisionEngine, InputEvent, DecisionOutcome
from engine.action_executor import ActionExecutor
from core.config_manager import ConfigManager


# ===========================================================================
# Mock Classes
# ===========================================================================

class MockCamera:
    """Mock camera that returns synthetic frames."""
    
    def __init__(self):
        self.frame_count = 0
        self.is_open = True
    
    def read(self):
        """Return synthetic BGR frame."""
        self.frame_count += 1
        # Mock frame: 480x640x3 BGR uint8
        import numpy as np
        frame = np.zeros((480, 640, 3), dtype="uint8")
        return True, frame
    
    def release(self):
        self.is_open = False
    
    def set(self, prop, value):
        pass


class MockHandTracker:
    """Mock hand tracker that returns synthetic landmarks."""
    
    def __init__(self):
        self.detect_count = 0
        self.gesture_override = None
    
    def detect_hands(self, frame):
        """Return mock hand landmarks."""
        self.detect_count += 1
        import numpy as np
        # Mock: 21 landmarks (x, y, z) per hand
        landmarks = np.random.rand(21, 3).astype("float32")
        return [(landmarks, 0)], 0.95  # (hand_landmarks, hand_index), confidence
    
    def close(self):
        pass


class MockGestureClassifier:
    """Mock gesture classifier with configurable output."""
    
    SUPPORTED_GESTURES = {
        "open_palm": "Open Palm",
        "pinch": "Pinch",
        "three_fingers": "Three Fingers",
        "fist": "Fist",
        "two_fingers": "Two Fingers",
    }
    
    def __init__(self):
        self.classify_count = 0
        self.gesture_override = None
    
    def set_gesture(self, gesture: str):
        """Override the gesture returned by classify()."""
        self.gesture_override = gesture
    
    def classify(self, landmarks):
        """Return mock gesture classification."""
        self.classify_count += 1
        if self.gesture_override:
            gesture = self.gesture_override
            self.gesture_override = None  # One-time override
        else:
            gesture = "Open Palm"
        
        return gesture, 0.92  # (gesture_name, confidence)


class MockVoiceListener:
    """Mock voice listener with configurable commands."""
    
    def __init__(self):
        self.commands_queue = []
        self.poll_count = 0
    
    def queue_command(self, command: str, confidence: float = 0.9):
        """Queue a command to be returned by poll_latest()."""
        self.commands_queue.append((command, confidence))
    
    def poll_latest(self):
        """Return latest queued command."""
        self.poll_count += 1
        if self.commands_queue:
            return self.commands_queue.pop(0)
        return None


class SpyActionExecutor(ActionExecutor):
    """Mock ActionExecutor that tracks calls instead of executing."""
    
    def __init__(self):
        # Don't call parent __init__ to avoid real setup
        self.call_log = []
        self.action_count = 0
        self.last_action = None
        self.should_fail = False
    
    def execute(self, action: str) -> bool:
        """Log action call instead of executing."""
        self.action_count += 1
        self.last_action = action
        self.call_log.append({
            "action": action,
            "count": self.action_count,
        })
        
        if self.should_fail:
            return False
        return True
    
    def was_called_with(self, action: str) -> bool:
        """Check if action was called."""
        return any(call["action"] == action for call in self.call_log)
    
    def call_count(self, action: str = None) -> int:
        """Get call count for action (or total if action is None)."""
        if action is None:
            return self.action_count
        return sum(1 for call in self.call_log if call["action"] == action)
    
    def reset(self):
        """Clear call log."""
        self.call_log = []
        self.action_count = 0
        self.last_action = None


class MockFaceSecurityManager:
    """Mock face security manager with configurable authorization."""
    
    def __init__(self):
        self.is_authorized = True
        self.face_detected = True
        self.evaluate_count = 0
        self.authorization_override = None
        self.current_session = None
        self.required_auth_actions = set()
    
    def set_authorization(self, authorized: bool, detected: bool = True):
        """Override authorization result."""
        self.authorization_override = (authorized, detected)
    
    def evaluate(self):
        """Return mock face auth result."""
        self.evaluate_count += 1
        
        if self.authorization_override:
            authorized, detected = self.authorization_override
            self.authorization_override = None
        else:
            authorized = self.is_authorized
            detected = self.face_detected
        
        # Return dict mimicking FaceAuthResult structure
        return {
            "is_authorized": authorized,
            "status_text": "Face Auth: Authorized" if authorized else "Face Auth: Unauthorized",
            "face_detected": detected,
            "user_present": detected,
            "system_paused": not authorized and detected,
        }

    def create_test_encoding(self):
        """Create deterministic mock face encoding."""
        return [0.1] * 128

    def recognize_face(self, face_data):
        """Recognize face and create session when authorized."""
        if face_data.get("authorized"):
            self.current_session = {
                "authenticated": True,
                "authorized": True,
                "user": face_data.get("user"),
            }
            return self.current_session
        return None

    def create_session(self, face_data):
        """Create session object for tests."""
        self.current_session = {
            "authenticated": bool(face_data.get("authorized", False)),
            "user": face_data.get("user"),
        }
        return self.current_session

    def expire_session(self):
        """Expire current session."""
        self.current_session = None

    def set_user_mode(self, user):
        """Set active user for compatibility with security tests."""
        if self.current_session is None:
            self.current_session = {}
        self.current_session["user"] = user

    def require_auth_for_action(self, action):
        """Track actions that require authentication."""
        self.required_auth_actions.add(action)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def config_manager():
    """Provide a ConfigManager instance."""
    return ConfigManager()


@pytest.fixture
def mock_camera():
    """Provide mock camera."""
    return MockCamera()


@pytest.fixture
def mock_hand_tracker():
    """Provide mock hand tracker."""
    return MockHandTracker()


@pytest.fixture
def mock_gesture_classifier():
    """Provide mock gesture classifier."""
    return MockGestureClassifier()


@pytest.fixture
def mock_voice_listener():
    """Provide mock voice listener."""
    return MockVoiceListener()


@pytest.fixture
def spy_action_executor():
    """Provide spy ActionExecutor."""
    return SpyActionExecutor()


@pytest.fixture
def mock_face_security():
    """Provide mock face security manager."""
    return MockFaceSecurityManager()


@pytest.fixture
def face_security(mock_face_security):
    """Backward-compatible alias expected by security-focused tests."""
    return mock_face_security


@pytest.fixture
def decision_engine(config_manager):
    """Provide DecisionEngine with ConfigManager."""
    engine = DecisionEngine(config_manager=config_manager)
    return engine


@pytest.fixture
def mmgi_pipeline(config_manager, decision_engine, spy_action_executor, mock_face_security):
    """
    Provide complete MMGI pipeline with all mocks integrated.
    
    Returns dict with all components for easy access in tests.
    """
    return {
        "config_manager": config_manager,
        "decision_engine": decision_engine,
        "action_executor": spy_action_executor,
        "face_security": mock_face_security,
    }


@pytest.fixture
def gesture_input_event():
    """Factory fixture to create gesture InputEvent."""
    def _make_event(gesture: str, mode: str = "App Mode", confidence: float = 0.95):
        return InputEvent(
            type="gesture",
            command=gesture,
            confidence=confidence,
            timestamp=None,
            mode=mode,
        )
    return _make_event


@pytest.fixture
def voice_input_event():
    """Factory fixture to create voice InputEvent."""
    def _make_event(command: str, mode: str = "App Mode", confidence: float = 0.9):
        return InputEvent(
            type="voice",
            command=command,
            confidence=confidence,
            timestamp=None,
            mode=mode,
        )
    return _make_event


# ===========================================================================
# Helpers
# ===========================================================================

def assert_action_executed(spy_executor: SpyActionExecutor, action: str, count: int = 1):
    """Assert that an action was executed expected number of times."""
    actual_count = spy_executor.call_count(action)
    assert actual_count == count, f"Expected {action} to be called {count} times, got {actual_count}"


# ===========================================================================
# Extended Fixtures for Comprehensive Testing
# ===========================================================================

@pytest.fixture
def gesture_event(spy_action_executor):
    """Factory fixture for creating gesture events."""
    def factory(gesture_name="palm_open", confidence=0.95, mode=None):
        return InputEvent(
            type="gesture",
            command=gesture_name,
            confidence=confidence,
            timestamp=None,
            mode=mode,
        )
    return factory


@pytest.fixture
def gesture_history():
    """Track gesture history for testing."""
    return []


@pytest.fixture
def voice_history():
    """Track voice history for testing."""
    return []


@pytest.fixture
def test_configs():
    """Test configuration data."""
    return {
        "gesture_confidence_threshold": 0.5,
        "voice_confidence_threshold": 0.6,
        "fusion_timeout_ms": 200,
        "max_input_buffer_size": 100,
    }


@pytest.fixture
def mock_metrics():
    """Mock metrics collector."""
    metrics = Mock()
    metrics.latencies = []
    metrics.throughput = 0
    metrics.error_count = 0
    
    def record_latency(latency):
        metrics.latencies.append(latency)
    
    def get_avg_latency():
        return sum(metrics.latencies) / len(metrics.latencies) if metrics.latencies else 0
    
    metrics.record_latency = record_latency
    metrics.get_avg_latency = get_avg_latency
    
    return metrics


@pytest.fixture(autouse=True)
def reset_mocks(spy_action_executor):
    """Reset mocks before each test."""
    yield
    spy_action_executor.reset()


# ===========================================================================
# Test Markers
# ===========================================================================

def pytest_configure(config):
    """Register pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )
    config.addinivalue_line(
        "markers", "stress: mark test as stress test"
    )


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--run-performance", action="store_true", default=False, help="run performance tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    if not config.getoption("--run-performance"):
        skip_perf = pytest.mark.skip(reason="need --run-performance option to run")
        for item in items:
            if "performance" in item.keywords:
                item.add_marker(skip_perf)


def assert_action_not_executed(spy_executor: SpyActionExecutor, action: str):
    """Assert that an action was NOT executed."""
    assert not spy_executor.was_called_with(action), f"Expected {action} not to be called"


def assert_last_action(spy_executor: SpyActionExecutor, action: str):
    """Assert that the last executed action matches."""
    assert spy_executor.last_action == action, f"Expected last action to be {action}, got {spy_executor.last_action}"
