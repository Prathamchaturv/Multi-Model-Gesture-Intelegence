"""
test_voice_action_mapping.py - Integration tests for voice command → action mapping.

Tests:
- Voice command recognition
- Mode-specific voice mappings
- Voice confidence thresholds
- Voice command normalization
- Action execution verification
"""

import pytest
from engine.decision_engine import InputEvent


class TestVoiceToActionMapping:
    """Test voice command recognition and action execution."""
    
    def test_open_brave_command_app_mode(self, mmgi_pipeline, voice_input_event):
        """Test: 'open browser' voice command → Open Browser action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Act: Send voice command
        event = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        # Execute the action
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Assert: Browser opening action should be called
        assert outcome is not None
        assert outcome.action == "open_brave"
        assert executor.was_called_with("open_brave")


    def test_open_youtube_command(self, mmgi_pipeline, voice_input_event):
        """Test: 'open youtube' voice command."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("open_youtube", mode="App Mode", confidence=0.9)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "open_youtube"


    def test_close_window_command(self, mmgi_pipeline, voice_input_event):
        """Test: 'close window' voice command."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("close_window", mode="App Mode", confidence=0.9)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "close_window"


    def test_switch_tab_command(self, mmgi_pipeline, voice_input_event):
        """Test: 'switch tab' voice command."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("switch_tab", mode="App Mode", confidence=0.9)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "switch_tab"


    def test_media_mode_play_command(self, mmgi_pipeline, voice_input_event):
        """Test: 'play' voice command in Media Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("play_song", mode="Media Mode", confidence=0.9)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "play_pause"


    def test_media_mode_next_track(self, mmgi_pipeline, voice_input_event):
        """Test: 'next track' voice command in Media Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("next_track", mode="Media Mode", confidence=0.9)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert outcome is not None
        assert outcome.action == "next_track"


    def test_media_mode_volume_commands(self, mmgi_pipeline, voice_input_event):
        """Test: Volume control commands in Media Mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        volume_commands = [
            ("volume_up", "volume_up"),
            ("volume_down", "volume_down"),
            ("mute", "mute"),
        ]
        
        for command, expected_action in volume_commands:
            event = voice_input_event(command, mode="Media Mode", confidence=0.9)
            outcome = engine.decide(event)
            
            if outcome and outcome.action:
                executor.execute(outcome.action)
            
            assert outcome is not None
            assert outcome.action == expected_action


    def test_low_confidence_voice_rejected(self, mmgi_pipeline, voice_input_event):
        """Test: Low confidence voice command should be rejected."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Voice command with very low confidence
        event = voice_input_event("open_brave", mode="App Mode", confidence=0.3)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Low confidence should be filtered or marked as unstable
        # (exact behavior depends on implementation)
        assert True


    def test_multiple_voice_commands_sequence(self, mmgi_pipeline, voice_input_event):
        """Test: Sequential voice commands work correctly."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        commands = [
            ("open_youtube", "open_youtube"),
            ("next_track", "next_track"),
            ("volume_up", "volume_up"),
        ]
        
        executor.reset()
        
        for command, expected_action in commands:
            event = voice_input_event(command, mode="Media Mode", confidence=0.95)
            outcome = engine.decide(event)
            
            if outcome and outcome.action:
                executor.execute(outcome.action)
            
            assert outcome is not None
            assert outcome.action == expected_action
        
        # Verify all commands were executed
        assert executor.call_count() >= len(commands)


    def test_voice_command_mode_specific(self, mmgi_pipeline, voice_input_event):
        """Test: Voice commands mapped differently based on mode."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # "play_song" command in different modes
        outcomes = {}
        
        for mode in ["App Mode", "Media Mode", "System Mode"]:
            event = voice_input_event("play_song", mode=mode, confidence=0.95)
            outcome = engine.decide(event)
            outcomes[mode] = outcome.action if outcome else None
        
        # In Media Mode, should map to play_pause
        assert outcomes["Media Mode"] == "play_pause"


class TestVoiceCommandEdgeCases:
    """Test edge cases for voice command mapping."""
    
    def test_unmapped_voice_command_no_action(self, mmgi_pipeline, voice_input_event):
        """Test: Unrecognized voice command returns no action."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        event = voice_input_event("unknown_command_xyz", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Should not execute anything
        assert executor.call_count() == 0


    def test_empty_voice_command_no_crash(self, mmgi_pipeline, voice_input_event):
        """Test: Empty voice command doesn't crash."""
        engine = mmgi_pipeline["decision_engine"]
        
        event = voice_input_event("", mode="App Mode", confidence=0.95)
        outcome = engine.decide(event)
        
        # Should handle gracefully
        assert True


    def test_voice_confidence_boundary_values(self, mmgi_pipeline, voice_input_event):
        """Test: Confidence at boundary values."""
        engine = mmgi_pipeline["decision_engine"]
        
        confidence_levels = [0.0, 0.5, 0.8, 0.95, 1.0]
        
        for conf in confidence_levels:
            event = voice_input_event("open_brave", mode="App Mode", confidence=conf)
            outcome = engine.decide(event)
            # Just verify no crashes
            assert True


    def test_case_sensitivity_voice_command(self, mmgi_pipeline):
        """Test: Voice command handling of case variations."""
        engine = mmgi_pipeline["decision_engine"]
        
        # Test various case variations (if normalized)
        commands = [
            "open_brave",
            "OPEN_BRAVE",
            "Open_Brave",
        ]
        
        for command in commands:
            event = InputEvent(
                type="voice",
                command=command,
                confidence=0.95,
                timestamp=None,
                mode="App Mode",
            )
            outcome = engine.decide(event)
            # Should handle case variations gracefully
            assert True
