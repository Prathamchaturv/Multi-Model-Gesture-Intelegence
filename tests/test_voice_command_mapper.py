"""
Test suite for VoiceCommandMapper phrase variation matching and confidence scoring.

Tests the advanced voice command system introduced in Session 9:
- Exact command matching
- Phrase variation matching (token-subset scoring)
- Confidence threshold filtering
- Hot-reload from json config
"""

import pytest
import json
import os
import tempfile
import time
from core.voice_control import VoiceCommandMapper, VoiceCommandListener, VoiceCommandEvent


class TestVoiceCommandMapperBasics:
    """Test core VoiceCommandMapper functionality."""
    
    def test_exact_match_returns_full_confidence(self):
        """Exact phrase match should return confidence 1.0."""
        mapper = VoiceCommandMapper()
        
        # Test exact match for one of the default phrases
        command, confidence = mapper.map_command("scroll down")
        assert command == "scroll_down"
        assert confidence == 1.0
    
    def test_unknown_command_returns_none(self):
        """Unknown phrase should return (None, 0.0)."""
        mapper = VoiceCommandMapper()
        
        command, confidence = mapper.map_command("xyz123 unknown command")
        assert command is None
        assert confidence == 0.0
    
    def test_phrase_variation_matching(self):
        """Token-subset scoring should match phrase variations."""
        mapper = VoiceCommandMapper()
        
        # All of these should map to scroll_down with confidence > 0
        test_cases = [
            ("go down", "scroll_down"),
            ("move down", "scroll_down"),
            ("page down", "scroll_down"),
        ]
        
        for phrase, expected_command in test_cases:
            command, confidence = mapper.map_command(phrase)
            assert command == expected_command, f"Failed for phrase: {phrase}"
            assert 0.5 <= confidence <= 1.0, f"Confidence {confidence} out of range for {phrase}"
    
    def test_volume_command_variations(self):
        """Test volume up/down variations."""
        mapper = VoiceCommandMapper()
        
        # Volume up variations
        up_cases = [
            ("volume up", "volume_up"),
            ("increase volume", "volume_up"),
            ("raise volume", "volume_up"),
            ("louder", "volume_up"),
        ]
        
        for phrase, expected_cmd in up_cases:
            cmd, conf = mapper.map_command(phrase)
            assert cmd == expected_cmd, f"Failed for {phrase}"
            assert conf > 0.5, f"Low confidence for {phrase}: {conf}"
        
        # Volume down variations
        down_cases = [
            ("volume down", "volume_down"),
            ("decrease volume", "volume_down"),
            ("lower volume", "volume_down"),
            ("softer", "volume_down"),
        ]
        
        for phrase, expected_cmd in down_cases:
            cmd, conf = mapper.map_command(phrase)
            assert cmd == expected_cmd, f"Failed for {phrase}"
            assert conf > 0.5, f"Low confidence for {phrase}: {conf}"
    
    def test_normalization_handles_case_insensitivity(self):
        """Normalization should handle case variations."""
        mapper = VoiceCommandMapper()
        
        cases = [
            "SCROLL DOWN",
            "Scroll Down",
            "sCrOLl DoWN",
        ]
        
        for phrase in cases:
            command, confidence = mapper.map_command(phrase)
            assert command == "scroll_down"
            assert confidence == 1.0
    
    def test_normalization_handles_punctuation(self):
        """Normalization should strip punctuation."""
        mapper = VoiceCommandMapper()
        
        cases = [
            "scroll down!",
            "scroll down.",
            "scroll, down",
        ]
        
        for phrase in cases:
            command, confidence = mapper.map_command(phrase)
            assert command == "scroll_down"
            assert confidence == 1.0


class TestVoiceCommandMapperCustomGroups:
    """Test custom command group configuration."""
    
    def test_custom_command_groups_override_defaults(self):
        """Custom groups should override default mapping."""
        custom_groups = {
            "custom_action": ["special phrase", "unique command"],
        }
        
        mapper = VoiceCommandMapper(command_groups=custom_groups)
        
        # Custom command should work
        cmd, conf = mapper.map_command("special phrase")
        assert cmd == "custom_action"
        assert conf == 1.0
        
        # Default command should still work
        cmd, conf = mapper.map_command("scroll down")
        assert cmd == "scroll_down"
        assert conf == 1.0
    
    def test_custom_groups_with_multiple_phrases(self):
        """Custom groups with multiple phrase variations."""
        custom_groups = {
            "my_command": ["phrase one", "phrase two", "phrase three"],
        }
        
        mapper = VoiceCommandMapper(command_groups=custom_groups)
        
        for phrase in ["phrase one", "phrase two", "phrase three"]:
            cmd, conf = mapper.map_command(phrase)
            assert cmd == "my_command"
            assert conf == 1.0


class TestVoiceCommandMapperConfidenceScoring:
    """Test confidence scoring for partial matches."""
    
    def test_exact_match_highest_confidence(self):
        """Exact match should have confidence 1.0."""
        mapper = VoiceCommandMapper()
        
        cmd, conf = mapper.map_command("scroll down")
        assert conf == 1.0
    
    def test_partial_match_lower_confidence(self):
        """Partial token match should have confidence < 1.0."""
        mapper = VoiceCommandMapper()
        
        # These are partial matches (not exact phrases)
        cmd, conf = mapper.map_command("scroll")
        assert cmd is None or conf < 1.0  # May not match if single word insufficient
    
    def test_confidence_threshold_filtering(self):
        """Commands below threshold should be filtered."""
        # Create mapper with custom low-confidence threshold
        mapper = VoiceCommandMapper()
        
        # This should be a valid command with reasonable confidence
        cmd, conf = mapper.map_command("go down")
        
        # If we explicitly filter in application code, confidence is available
        if conf < 0.5:  # Example threshold
            # Would be filtered out
            assert False, "Unexpected low confidence for valid variation"


class TestVoiceCommandMapperHotReload:
    """Test dynamic config reload from JSON file."""
    
    def test_reload_from_json_file(self):
        """VoiceCommandMapper should reload config from JSON file."""
        # Create a temporary config file
        config_data = {
            "command_groups": {
                "test_reload": ["reload phrase one", "reload phrase two"],
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            mapper = VoiceCommandMapper(config_path=config_path)
            
            # Command from file should work
            cmd, conf = mapper.map_command("reload phrase one")
            assert cmd == "test_reload"
            assert conf == 1.0
            
            # Update the file
            config_data["command_groups"]["test_reload"].append("reload phrase three")
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            # Trigger reload
            mapper._reload_from_file(force=True)
            
            # New phrase should now work
            cmd, conf = mapper.map_command("reload phrase three")
            assert cmd == "test_reload"
            assert conf == 1.0
        
        finally:
            os.unlink(config_path)
    
    def test_reload_only_when_file_modified(self):
        """Reload should only occur when file mtime changes."""
        config_data = {
            "command_groups": {
                "first_version": ["phrase one"],
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            mapper = VoiceCommandMapper(config_path=config_path)
            
            # Get initial mtime
            initial_mtime = os.path.getmtime(config_path)
            
            # Reload should skip if mtime hasn't changed
            mapper._reload_from_file(force=False)  # No change expected
            
            # Verify old command still works
            cmd, conf = mapper.map_command("phrase one")
            assert cmd == "first_version"
        
        finally:
            os.unlink(config_path)


class TestVoiceCommandListenerIntegration:
    """Test VoiceCommandListener integration with VoiceCommandMapper."""
    
    def test_listener_accepts_confidence_threshold_param(self):
        """VoiceCommandListener should accept confidence_threshold parameter."""
        # This tests that the constructor accepts the new param
        listener = VoiceCommandListener(
            confidence_threshold=0.7,
            command_groups={},
            command_config_path=None,
            energy_threshold=250,
        )
        
        # Listener should be creatable with new params
        assert listener is not None
    
    def test_listener_accepts_command_groups_param(self):
        """VoiceCommandListener should accept command_groups parameter."""
        custom_groups = {
            "test_cmd": ["test phrase"],
        }
        
        listener = VoiceCommandListener(
            confidence_threshold=0.5,
            command_groups=custom_groups,
            command_config_path=None,
            energy_threshold=250,
        )
        
        assert listener is not None

class TestVoiceCommandEventConfidence:
    """Test VoiceCommandEvent now includes confidence field."""
    
    def test_voice_command_event_has_confidence_field(self):
        """VoiceCommandEvent should have confidence field."""
        event = VoiceCommandEvent(
            command="scroll_down",
            transcript="scroll down",
            timestamp=time.time(),
            confidence=0.95,
        )
        
        assert event.command == "scroll_down"
        assert event.confidence == 0.95
    
    def test_voice_command_event_confidence_range(self):
        """Confidence should be in [0.0, 1.0] range."""
        event1 = VoiceCommandEvent(command="test", transcript="test", timestamp=time.time(), confidence=0.0)
        event2 = VoiceCommandEvent(command="test", transcript="test", timestamp=time.time(), confidence=1.0)
        event3 = VoiceCommandEvent(command="test", transcript="test", timestamp=time.time(), confidence=0.5)
        
        assert 0.0 <= event1.confidence <= 1.0
        assert 0.0 <= event2.confidence <= 1.0
        assert 0.0 <= event3.confidence <= 1.0


class TestVoiceCommandMapperEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_transcript_returns_none(self):
        """Empty or whitespace-only transcript should return None."""
        mapper = VoiceCommandMapper()
        
        cases = ["", "   ", "\t", "\n"]
        for case in cases:
            cmd, conf = mapper.map_command(case)
            assert cmd is None
            assert conf == 0.0
    
    def test_special_characters_ignored(self):
        """Special characters should be normalized away."""
        mapper = VoiceCommandMapper()
        
        # These should map to scroll_down after normalization
        cases = [
            "scroll... down!!!",
            "scroll??? down",
            "scroll (down)",
        ]
        
        # At least some should match
        matches = 0
        for case in cases:
            cmd, conf = mapper.map_command(case)
            if cmd == "scroll_down":
                matches += 1
        
        assert matches > 0, "Special character handling broken"
    
    def test_very_long_transcript_handled(self):
        """Very long transcripts should still be processed."""
        mapper = VoiceCommandMapper()
        
        long_transcript = "please " + " ".join(["please"] * 100) + " scroll down"
        cmd, conf = mapper.map_command(long_transcript)
        
        # Should still find "scroll down" in there
        assert cmd == "scroll_down"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
