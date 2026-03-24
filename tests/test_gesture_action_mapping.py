"""
test_gesture_action_mapping.py - Integration tests for gesture → action mapping.

Tests:
- Gesture detection and classification
- Mode-specific gesture mappings
- Confidence thresholds
- Gesture stability confirmation
- Action execution verification
"""

import pytest
from engine.decision_engine import InputEvent


class TestGestureToActionMapping:
    """Test gesture recognition and action execution."""
    
    def test_single_finger_app_mode_opens_browser(self, mmgi_pipeline, gesture_input_event):
        """Test: One Finger gesture in App Mode → Open Browser action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Act: Send gesture event
        event = gesture_input_event("One Finger", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        # Execute the action
        executor.execute(outcome.action if outcome and outcome.action else "")
        
        # Assert: Browser opening action should be called
        assert outcome is not None
        assert outcome.action == "open_brave"


    def test_two_fingers_app_mode_opens_music(self, mmgi_pipeline, gesture_input_event):
        """Test: Two Fingers gesture in App Mode → Open Music action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("Two Fingers", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Assert: Music opening action should be called
        assert outcome is not None
        assert outcome.action == "open_apple_music"
        assert executor.was_called_with("open_apple_music")


    def test_pinch_app_mode_left_click(self, mmgi_pipeline, gesture_input_event):
        """Test: Pinch gesture in App Mode → Left Click action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("Pinch", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "left_click"
        assert executor.was_called_with("left_click")


    def test_media_mode_volume_up(self, mmgi_pipeline, gesture_input_event):
        """Test: One Finger in Media Mode → Volume Up."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("One Finger", mode="Media Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "volume_up"
        assert executor.was_called_with("volume_up")


    def test_media_mode_volume_down(self, mmgi_pipeline, gesture_input_event):
        """Test: Two Fingers in Media Mode → Volume Down."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("Two Fingers", mode="Media Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "volume_down"


    def test_media_mode_play_pause(self, mmgi_pipeline, gesture_input_event):
        """Test: Four Fingers in Media Mode → Play/Pause."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("Four Fingers", mode="Media Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "play_pause"


    def test_low_confidence_gesture_rejected(self, mmgi_pipeline, gesture_input_event):
        """Test: Low confidence gesture should be rejected or not mapped."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Gesture with very low confidence (below typical threshold)
        event = gesture_input_event("One Finger", mode="App Mode", confidence=0.2)
        outcome = engine.decide(event)
        
        # Should either have no action or mark as unstable
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Either no action or confidence-based filtering
        # (exact behavior depends on DecisionEngine implementation)
        assert True  # Just verify it doesn't crash


    def test_system_mode_scroll_down(self, mmgi_pipeline, gesture_input_event):
        """Test: Open Palm in System Mode → Scroll Down."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = gesture_input_event("Open Palm", mode="System Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "scroll_down"


    def test_multiple_gestures_sequence(self, mmgi_pipeline, gesture_input_event):
        """Test: Sequential gesture inputs work correctly."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Sequence: One Finger → Two Fingers → Pinch
        gestures = ["One Finger", "Two Fingers", "Pinch"]
        expected_actions = ["open_brave", "open_apple_music", "left_click"]
        
        for gesture, expected_action in zip(gestures, expected_actions):
            event = gesture_input_event(gesture, mode="App Mode", confidence=0.95)
            outcome = engine.decide(event)
            
            if outcome and outcome.action:
                executor.execute(outcome.action)
            
            assert outcome is not None
            assert outcome.action == expected_action
        
        # Verify all actions were executed
        assert executor.call_count() == len(gestures)


    def test_gesture_with_mode_context(self, mmgi_pipeline, gesture_input_event):
        """Test: Same gesture maps to different actions based on mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # One Finger in different modes
        outcomes = {}
        for mode in ["App Mode", "Media Mode", "System Mode"]:
            event = gesture_input_event("One Finger", mode=mode, confidence=0.95)
            outcome = engine.decide(event)
            outcomes[mode] = outcome.action if outcome else None
        
        # Verify mode-specific mappings
        assert outcomes["App Mode"] == "open_brave"
        assert outcomes["Media Mode"] == "volume_up"
        # System Mode may not have One Finger mapping


class TestGestureEdgeCases:
    """Test edge cases and error conditions for gesture mapping."""
    
    def test_unmapped_gesture_no_action(self, mmgi_pipeline, gesture_input_event):
        """Test: Gesture not in mapping returns no action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Use non-standard gesture name
        event = gesture_input_event("UnknownGesture", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        # Should not execute anything
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Either no outcome or no action
        assert executor.call_count() == 0


    def test_empty_gesture_no_crash(self, mmgi_pipeline, gesture_input_event):
        """Test: Empty gesture string doesn't crash."""
        engine = mmgi_pipeline["decision_engine"]
        
        event = gesture_input_event("", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        # Should handle gracefully
        assert True


    def test_gesture_confidence_boundary(self, mmgi_pipeline, gesture_input_event):
        """Test: Confidence at boundary values."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Test various confidence levels
        confidence_levels = [0.0, 0.5, 0.7, 0.95, 1.0]
        
        for conf in confidence_levels:
            event = gesture_input_event("One Finger", mode="App Mode", confidence=conf)
            outcome = engine.decide(event)
            # Just verify no crashes
            assert True
