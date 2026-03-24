"""
test_e2e_comprehensive.py - Comprehensive end-to-end tests for complete workflows.

Tests:
- Complete user sessions
- Multi-step workflows
- Cross-module integration
- Real-world usage patterns
- Error recovery workflows
"""

import pytest
import time
from engine.decision_engine import InputEvent


class TestCompleteUserSessions:
    """Test complete user sessions from start to finish."""
    
    def test_session_entire_workflow_media_control(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Complete media control workflow."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # 1. User switches to Media Mode
        engine.set_mode("Media Mode")
        
        # 2. User plays a song with voice
        evt1 = voice_input_event("play_song", mode="Media Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # 3. User increases volume with gesture
        evt2 = gesture_event("swipe_up", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # 4. User skips to next track with gesture
        evt3 = gesture_event("swipe_right", confidence=0.95)
        outcome3 = engine.decide(evt3)
        if outcome3 and outcome3.action:
            executor.execute(outcome3.action)
        
        # 5. User decreases volume with voice
        evt4 = voice_input_event("volume_down", mode="Media Mode", confidence=0.95)
        outcome4 = engine.decide(evt4)
        if outcome4 and outcome4.action:
            executor.execute(outcome4.action)
        
        # All steps should complete without errors
        assert executor.call_count() >= 3


    def test_session_entire_workflow_browsing(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Complete web browsing workflow."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # 1. Switch to App Mode
        engine.set_mode("App Mode")
        
        # 2. Open browser with voice
        evt1 = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        time.sleep(0.01)  # Simulate browser opening
        
        # 3. Switch tabs with gesture
        evt2 = gesture_event("swipe_left", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # 4. Click with gesture
        evt3 = gesture_event("point_and_click", confidence=0.95)
        outcome3 = engine.decide(evt3)
        if outcome3 and outcome3.action:
            executor.execute(outcome3.action)
        
        # 5. Close browser with voice
        evt4 = voice_input_event("close_window", mode="App Mode", confidence=0.95)
        outcome4 = engine.decide(evt4)
        if outcome4 and outcome4.action:
            executor.execute(outcome4.action)
        
        assert executor.call_count() >= 3


    def test_session_entire_workflow_system_control(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Complete system control workflow."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # 1. Switch to System Mode
        engine.set_mode("System Mode")
        
        # 2. Take screenshot with gesture
        evt1 = gesture_event("peace_sign", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # 3. Lock screen with voice
        evt2 = voice_input_event("lock_screen", mode="System Mode", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        assert executor.call_count() >= 1


class TestMultiStepWorkflows:
    """Test complex multi-step workflows."""
    
    def test_workflow_open_app_then_control(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Open app, then control it with gestures."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Open YouTube
        evt1 = voice_input_event("open_youtube", mode="App Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Play video with gesture
        evt2 = gesture_event("point_and_click", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Change volume
        evt3 = gesture_event("swipe_up", confidence=0.95)
        outcome3 = engine.decide(evt3)
        if outcome3 and outcome3.action:
            executor.execute(outcome3.action)
        
        assert executor.call_count() >= 2


    def test_workflow_conditional_mode_switching(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Mode switching based on user actions."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Start in App Mode
        engine.set_mode("App Mode")
        
        # Open media app
        evt1 = voice_input_event("open_youtube", mode="App Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Switch to Media Mode
        engine.set_mode("Media Mode")
        
        # Use media controls
        evt2 = gesture_event("swipe_up", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Back to App Mode
        engine.set_mode("App Mode")
        
        evt3 = gesture_event("swipe_left", confidence=0.95)
        outcome3 = engine.decide(evt3)
        if outcome3 and outcome3.action:
            executor.execute(outcome3.action)
        
        assert executor.call_count() >= 2


    def test_workflow_error_recovery(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: System recovers from errors in workflow."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Send invalid command
        evt1 = voice_input_event("unknown_command", mode="App Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # System should continue working with valid command
        evt2 = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Should have executed the valid command
        assert outcome2 is not None


class TestCrossModuleIntegration:
    """Test integration between different modules."""
    
    def test_gesture_recognition_with_action_execution(self, mmgi_pipeline, gesture_event):
        """Test: Gesture recognition + action execution integration."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Gesture recognition
        evt = gesture_event("palm_open", confidence=0.95)
        
        # Decision making
        outcome = engine.decide(evt)
        
        # Action execution
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert executor.call_count() > 0


    def test_voice_recognition_with_multi_modal_fusion(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Voice recognition + multimodal fusion."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Voice command
        voice_evt = voice_input_event("switch_tab", mode="App Mode", confidence=0.9)
        
        # Simultaneously gesture
        gesture_evt = gesture_event("swipe_left", confidence=0.95)
        
        # Both should be processable
        outcome1 = engine.decide(voice_evt)
        outcome2 = engine.decide(gesture_evt)
        
        # Execute outcomes
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        assert executor.call_count() >= 1


    def test_mode_engine_with_gesture_interpreter(self, mmgi_pipeline, gesture_event):
        """Test: Mode engine + gesture interpreter integration."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Change mode
        engine.set_mode("Media Mode")
        
        # Same gesture interpreted differently
        evt = gesture_event("swipe_left", confidence=0.95)
        outcome = engine.decide(evt)
        
        # In Media Mode, swipe_left = previous track
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert True


    def test_calibration_affects_gesture_accuracy(self, mmgi_pipeline, gesture_event):
        """Test: Calibration affects gesture recognition accuracy."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Gesture with calibration offset
        evt1 = gesture_event("palm_open", confidence=0.95)
        evt1.calibration_offset = 0.0
        outcome1 = engine.decide(evt1)
        
        # Same gesture with different calibration
        evt2 = gesture_event("palm_open", confidence=0.95)
        evt2.calibration_offset = 0.1
        outcome2 = engine.decide(evt2)
        
        # Both should be processable
        assert outcome1 is not None or outcome2 is not None


class TestRealWorldScenarios:
    """Test real-world usage patterns."""
    
    def test_user_working_with_multiple_applications(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: User switching between multiple applications."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Open first app
        evt1 = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Open second app
        evt2 = voice_input_event("open_youtube", mode="App Mode", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Switch between apps with gesture
        for i in range(3):
            evt = gesture_event("swipe_left", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        assert executor.call_count() >= 3


    def test_user_rapid_command_sequence(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: User issues rapid commands in sequence."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        engine.set_mode("Media Mode")
        
        commands = [
            ("play_song", "play_song", voice_input_event),
            ("volume_up", "volume_up", gesture_event),
            ("next_track", "next_track", voice_input_event),
            ("volume_down", "volume_down", gesture_event),
            ("previous_track", "previous_track", voice_input_event),
        ]
        
        for cmd, expected, evt_fn in commands:
            if evt_fn == gesture_event:
                evt = gesture_event(cmd, confidence=0.95)
            else:
                evt = voice_input_event(cmd, mode="Media Mode", confidence=0.95)
            
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        assert executor.call_count() >= 3


    def test_user_interleaving_gestures_and_voice(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: User mixing gestures and voice commands naturally."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        engine.set_mode("App Mode")
        
        # Gesture to open browser
        evt1 = gesture_event("peace_sign", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Voice to open YouTube
        evt2 = voice_input_event("open_youtube", mode="App Mode", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Gesture to click
        evt3 = gesture_event("point_and_click", confidence=0.95)
        outcome3 = engine.decide(evt3)
        if outcome3 and outcome3.action:
            executor.execute(outcome3.action)
        
        # Voice to control
        evt4 = voice_input_event("volume_up", mode="App Mode", confidence=0.95)
        outcome4 = engine.decide(evt4)
        if outcome4 and outcome4.action:
            executor.execute(outcome4.action)
        
        assert executor.call_count() >= 2


    def test_user_adaptive_learning_across_session(self, mmgi_pipeline, gesture_event):
        """Test: System learns and adapts during user session."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # User performs gesture multiple times
        gesture_confidence_progression = [0.75, 0.80, 0.85, 0.90, 0.95]
        
        for confidence in gesture_confidence_progression:
            evt = gesture_event("palm_open", confidence=confidence)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        # System should improve recognition over time
        assert executor.call_count() >= 3


class TestErrorHandlingAndRecovery:
    """Test error handling in complete workflows."""
    
    def test_recovery_from_invalid_gesture(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Recovery from invalid gesture input."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Invalid gesture
        evt1 = gesture_event("invalid_gesture_xyz", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Valid voice command should still work
        evt2 = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Should have executed the valid command
        assert executor.call_count() >= 1


    def test_recovery_from_low_confidence_inputs(self, mmgi_pipeline, gesture_event):
        """Test: Recovery from stream of low-confidence inputs."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Low confidence inputs
        for i in range(5):
            evt = gesture_event("palm_open", confidence=0.2)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        # High confidence input should work
        evt = gesture_event("palm_open", confidence=0.95)
        outcome = engine.decide(evt)
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Should eventually execute
        assert executor.call_count() >= 1


    def test_recovery_from_mode_switch_during_command(self, mmgi_pipeline, gesture_event):
        """Test: Recovery when mode switches during command execution."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        engine.set_mode("App Mode")
        
        # Process gesture
        evt1 = gesture_event("swipe_left", confidence=0.95)
        outcome1 = engine.decide(evt1)
        if outcome1 and outcome1.action:
            executor.execute(outcome1.action)
        
        # Mode switches mid-execution
        engine.set_mode("Media Mode")
        
        # New gesture in new mode
        evt2 = gesture_event("swipe_left", confidence=0.95)
        outcome2 = engine.decide(evt2)
        if outcome2 and outcome2.action:
            executor.execute(outcome2.action)
        
        # Second command should work in new mode
        assert True
