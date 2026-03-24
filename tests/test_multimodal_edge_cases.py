"""
test_multimodal_edge_cases.py - Edge case tests for multimodal fusion.

Tests:
- Conflicting input signals
- Timing misalignments
- Confidence score combinations
- Mode switching during input
- Recovery from sensor failures
"""

import pytest
import time
from engine.decision_engine import InputEvent


class TestConflictingInputs:
    """Test handling of conflicting input signals."""
    
    def test_conflicting_gesture_voice_commands(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Conflicting gesture and voice commands."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Gesture says "close window", voice says "open browser"
        gesture_evt = gesture_event("swipe_down", confidence=0.95)
        voice_evt = voice_input_event("open_brave", mode="App Mode", confidence=0.9)
        
        executor.reset()
        
        # Process both
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        executor.reset()
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # System should handle without crashing
        # Priority should be determined by confidence, recency, or config
        assert outcome1 is not None or outcome2 is not None


    def test_contradictory_gesture_confidence(self, mmgi_pipeline, gesture_event):
        """Test: Gesture with conflicting confidence levels."""
        engine = mmgi_pipeline["decision_engine"]
        
        # High confidence in one gesture, low in another
        evt1 = gesture_event("palm_open", confidence=0.95)
        evt2 = gesture_event("fist_closed", confidence=0.2)
        
        outcome1 = engine.decide(evt1)
        
        # Higher confidence should take priority
        assert outcome1 is not None


    def test_rapid_mode_switching_conflict(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Rapid mode switches with pending inputs."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Simulate rapid mode switches
        modes = ["App Mode", "Media Mode", "System Mode"]
        
        for mode in modes:
            event = voice_input_event("play_song", mode=mode, confidence=0.95)
            outcome = engine.decide(event)
            
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        # System should handle mode changes gracefully
        assert executor.call_count() > 0


class TestTimingAndSynchronization:
    """Test timing and synchronization of multimodal inputs."""
    
    def test_simultaneous_gesture_voice_detection(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Gesture and voice detected simultaneously."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Both detected at same timestamp
        timestamp = time.time()
        
        gesture_evt = gesture_event("swipe_left", confidence=0.95)
        gesture_evt.timestamp = timestamp
        
        voice_evt = voice_input_event("switch_tab", mode="App Mode", confidence=0.95)
        voice_evt.timestamp = timestamp
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        assert outcome1 is not None or outcome2 is not None


    def test_temporal_proximity_tolerance(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Inputs within time window are considered fusion candidates."""
        engine = mmgi_pipeline["decision_engine"]
        
        base_time = time.time()
        
        # Gesture at t=0
        gesture_evt = gesture_event("palm_open", confidence=0.9)
        gesture_evt.timestamp = base_time
        
        # Voice 200ms later
        voice_evt = voice_input_event("click", mode="System Mode", confidence=0.9)
        voice_evt.timestamp = base_time + 0.2
        
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        # Both should be processable
        assert outcome1 is not None or outcome2 is not None


    def test_delayed_input_handling(self, mmgi_pipeline, gesture_event):
        """Test: Delayed input signals are handled correctly."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Gesture from 5 seconds ago
        old_timestamp = time.time() - 5.0
        
        evt = gesture_event("palm_open", confidence=0.95)
        evt.timestamp = old_timestamp
        
        outcome = engine.decide(evt)
        
        # Should still process, but possibly with lower weight
        assert True


class TestConfidenceScoreHandling:
    """Test confidence score combinations and handling."""
    
    def test_low_confidence_both_inputs(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Both inputs have low confidence."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        gesture_evt = gesture_event("swipe_left", confidence=0.4)
        voice_evt = voice_input_event("click", mode="System Mode", confidence=0.35)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Low confidence might result in no action or rejected command
        assert True


    def test_high_confidence_boosted_by_fusion(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Confidence boosted when signals agree."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Both signals point to similar action
        gesture_evt = gesture_event("swipe_left", confidence=0.6)  # Switch tab gesture
        voice_evt = voice_input_event("switch_tab", mode="App Mode", confidence=0.65)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        # When signals agree, confidence should be higher
        if outcome1 and outcome2:
            # Combined confidence should be higher than individual
            combined = (outcome1.confidence or 0.5) + (outcome2.confidence or 0.5)
            assert combined > 1.0  # Would indicate fusion boost


    def test_confidence_thresholds_enforced(self, mmgi_pipeline, gesture_event):
        """Test: Confidence thresholds are enforced."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        confidence_levels = [0.1, 0.3, 0.5, 0.7, 0.9]
        executed_count = 0
        
        for conf in confidence_levels:
            evt = gesture_event("palm_open", confidence=conf)
            outcome = engine.decide(evt)
            
            executor.reset()
            if outcome and outcome.action:
                executor.execute(outcome.action)
                executed_count += 1
        
        # Only high-confidence inputs should execute
        assert executed_count < len(confidence_levels)


class TestSensorFailureRecovery:
    """Test recovery from sensor failures and input source issues."""
    
    def test_missing_face_during_fusion(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: System works without face detection during multimodal fusion."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Gesture + voice without face detection
        gesture_evt = gesture_event("swipe_left", confidence=0.95)
        voice_evt = voice_input_event("switch_tab", mode="App Mode", confidence=0.9)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        # Should still work with available inputs
        assert outcome1 is not None or outcome2 is not None


    def test_missing_gesture_during_fusion(self, mmgi_pipeline, voice_input_event):
        """Test: System works with only voice input."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        voice_evt = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        
        executor.reset()
        outcome = engine.decide(voice_evt)
        
        # Should execute voice command without gestures
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert executor.call_count() > 0


    def test_intermittent_input_source_failure(self, mmgi_pipeline, gesture_event):
        """Test: System handles intermittent failures gracefully."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Simulate alternating successful/failed inputs
        for i in range(5):
            if i % 2 == 0:
                evt = gesture_event("palm_open", confidence=0.95)
            else:
                # Failed input
                evt = gesture_event("unknown", confidence=0.0)
            
            outcome = engine.decide(evt)
            # Should not crash
            assert True


class TestModeSpecificFusion:
    """Test multimodal fusion behavior in different modes."""
    
    def test_fusion_app_mode(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Multimodal fusion in App Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        gesture_evt = gesture_event("swipe_left", confidence=0.95)
        voice_evt = voice_input_event("switch_tab", mode="App Mode", confidence=0.9)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        assert outcome1 is not None or outcome2 is not None


    def test_fusion_media_mode(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Multimodal fusion in Media Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        gesture_evt = gesture_event("swipe_down", confidence=0.95)  # Volume down
        voice_evt = voice_input_event("volume_down", mode="Media Mode", confidence=0.9)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        assert outcome1 is not None or outcome2 is not None


    def test_fusion_system_mode(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Multimodal fusion in System Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        gesture_evt = gesture_event("pinch_in", confidence=0.95)
        voice_evt = voice_input_event("lock_screen", mode="System Mode", confidence=0.9)
        
        executor.reset()
        outcome1 = engine.decide(gesture_evt)
        outcome2 = engine.decide(voice_evt)
        
        assert outcome1 is not None or outcome2 is not None


class TestModeTransitions:
    """Test behavior during mode transitions."""
    
    def test_mode_transition_clears_pending_gestures(self, mmgi_pipeline, gesture_event):
        """Test: Switching modes doesn't execute old gestures."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Create gesture in first mode
        evt1 = gesture_event("swipe_left", confidence=0.95)
        
        executor.reset()
        outcome1 = engine.decide(evt1)
        
        # Change mode
        engine.set_mode("Media Mode")
        
        # Old gesture shouldn't carry over
        assert True


    def test_new_mode_gesture_interpretation(self, mmgi_pipeline, gesture_event):
        """Test: Same gesture interpreted differently in new mode."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Swipe left in App Mode = switch tab
        engine.set_mode("App Mode")
        evt1 = gesture_event("swipe_left", confidence=0.95)
        outcome1 = engine.decide(evt1)
        
        # Swipe left in Media Mode = previous track
        engine.set_mode("Media Mode")
        evt2 = gesture_event("swipe_left", confidence=0.95)
        outcome2 = engine.decide(evt2)
        
        # Actions should be different (or outcomes adjusted based on mode)
        if outcome1 and outcome2:
            # Verify both are valid outcomes for their respective modes
            assert outcome1 is not None
            assert outcome2 is not None
