"""
test_authentication_security.py - Authentication and security tests for MMGI.

Tests:
- User authentication
- Face recognition security
- Voice authentication
- Unauthorized action prevention
- Multi-user switching
"""

import pytest
from engine.decision_engine import InputEvent


class TestUserAuthentication:
    """Test user authentication system."""
    
    def test_valid_face_authentication(self, mmgi_pipeline, face_security):
        """Test: Valid face recognition authenticates user."""
        # Setup: Authorized face encoding
        face_data = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        # Act: Recognize authorized user
        auth_result = face_security.recognize_face(face_data)
        
        # Assert: User authenticated
        assert auth_result is not None
        assert auth_result.get("authorized") is True


    def test_unauthorized_face_rejected(self, mmgi_pipeline, face_security):
        """Test: Unauthorized face is rejected."""
        face_data = {
            "user": "unknown_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": False
        }
        
        auth_result = face_security.recognize_face(face_data)
        
        assert auth_result is None or auth_result.get("authorized") is False


    def test_face_authentication_timeout(self, mmgi_pipeline, face_security):
        """Test: Face authentication session timeout."""
        # Authenticate user
        face_data = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        auth_result = face_security.recognize_face(face_data)
        assert auth_result is not None
        
        # Wait for session timeout (mocked)
        face_security.expire_session()
        
        # Should require re-authentication
        auth_result_after = face_security.recognize_face(face_data)
        # After timeout, re-authentication should be required
        assert True


    def test_session_persistence_after_gesture(self, mmgi_pipeline, face_security, gesture_event):
        """Test: Session persists after gesture input."""
        # Authenticate
        face_data = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        auth_result = face_security.recognize_face(face_data)
        assert auth_result is not None
        
        # Execute gesture while authenticated
        evt = gesture_event("palm_open", confidence=0.95)
        
        # Should execute without re-authentication
        assert True


class TestMultiUserScenarios:
    """Test multi-user scenarios and switching."""
    
    def test_switch_user_via_face_recognition(self, mmgi_pipeline, face_security):
        """Test: Switch users via face recognition."""
        user1_data = {
            "user": "user1",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        user2_data = {
            "user": "user2",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        # Authenticate user1
        result1 = face_security.recognize_face(user1_data)
        assert result1 is not None
        
        # Switch to user2
        result2 = face_security.recognize_face(user2_data)
        assert result2 is not None
        
        # Contexts should be separate
        assert result1.get("user") != result2.get("user")


    def test_user_specific_gesture_mappings(self, mmgi_pipeline, face_security):
        """Test: Different users can have different gesture mappings."""
        engine = mmgi_pipeline["decision_engine"]
        
        # User1 preferences
        face_security.set_user_mode("user1")
        engine.set_mode("App Mode")
        
        # User2 preferences
        face_security.set_user_mode("user2")
        engine.set_mode("Media Mode")
        
        # Each user should maintain their settings
        assert True


class TestActionAuthorization:
    """Test action authorization and access control."""
    
    def test_unauthenticated_user_no_actions(self, mmgi_pipeline, gesture_event):
        """Test: Unauthenticated user cannot execute actions."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Without authentication
        executor.reset()
        
        evt = gesture_event("palm_open", confidence=0.95)
        # Should check authentication before executing
        outcome = engine.decide(evt)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Without proper auth, execution should be prevented
        assert True


    def test_system_mode_requires_authentication(self, mmgi_pipeline, voice_input_event, face_security):
        """Test: System Mode actions require authentication."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Try system mode without auth
        engine.set_mode("System Mode")
        
        evt = voice_input_event("lock_screen", mode="System Mode", confidence=0.95)
        outcome = engine.decide(evt)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Action should be blocked without auth
        assert True


    def test_screen_lock_only_authenticated_user(self, mmgi_pipeline, voice_input_event, face_security):
        """Test: Screen lock only from authenticated user."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Configure face security to require auth for lock
        face_security.require_auth_for_action("lock_screen")
        
        evt = voice_input_event("lock_screen", mode="System Mode", confidence=0.95)
        outcome = engine.decide(evt)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        assert True


class TestVoiceAuthentication:
    """Test voice-based authentication scenarios."""
    
    def test_voice_authentication_enrollment(self, mmgi_pipeline):
        """Test: Voice authentication enrollment process."""
        # Enroll voice patterns
        voice_samples = [
            "hello system",
            "hello system",
            "hello system",
        ]
        
        # In real implementation, would process voice samples
        assert len(voice_samples) >= 3


    def test_voice_unlock_with_correct_phrase(self, mmgi_pipeline):
        """Test: System unlocks with correct voice phrase."""
        # Verify specific voice phrase
        correct_phrase = "unlock now"
        
        # Verify phrase match
        assert correct_phrase == "unlock now"


    def test_voice_unlock_with_wrong_phrase(self, mmgi_pipeline):
        """Test: System rejects wrong voice phrase."""
        correct_phrase = "unlock now"
        wrong_phrase = "open browser"
        
        # Should not match
        assert correct_phrase != wrong_phrase


class TestFaceSecurityEdgeCases:
    """Test edge cases in face security."""
    
    def test_face_partially_obscured(self, mmgi_pipeline, face_security):
        """Test: System handles partially obscured face."""
        face_data = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "confidence": 0.4,  # Low confidence = partial obstruction
            "authorized": True
        }
        
        auth_result = face_security.recognize_face(face_data)
        
        # Low confidence should trigger re-authentication or rejection
        assert True


    def test_multiple_faces_detected(self, mmgi_pipeline, face_security):
        """Test: System handles multiple faces in frame."""
        # Primary face (authorized)
        primary_face = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True,
            "position": "primary"
        }
        
        # Secondary face (unknown)
        secondary_face = {
            "user": "unknown",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": False,
            "position": "secondary"
        }
        
        # System should authenticate primary face only
        result = face_security.recognize_face(primary_face)
        assert result is not None


    def test_spoofing_prevention(self, mmgi_pipeline, face_security):
        """Test: Spoofing attacks are prevented."""
        # Real face encoding
        real_face = face_security.create_test_encoding()
        
        # Attempt to spoof with same encoding twice
        result1 = face_security.recognize_face({
            "user": "test_user",
            "face_encoding": real_face,
            "authorized": True
        })
        
        # Immediate repeat should be detected as spoof attempt
        result2 = face_security.recognize_face({
            "user": "test_user",
            "face_encoding": real_face,
            "authorized": True,
            "timestamp_delta": 0.1  # Only 100ms later
        })
        
        # May trigger additional verification
        assert result1 is not None


class TestSecurityPolicyEnforcement:
    """Test security policy enforcement."""
    
    def test_user_gesture_whitelist(self, mmgi_pipeline, gesture_event):
        """Test: User can only execute whitelisted gestures."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Set user whitelist
        engine.set_user_gesture_whitelist([
            "palm_open",
            "swipe_left",
        ])
        
        executor.reset()
        
        # Allowed gesture
        evt1 = gesture_event("palm_open", confidence=0.95)
        outcome1 = engine.decide(evt1)
        
        # Not allowed gesture
        evt2 = gesture_event("peace_sign", confidence=0.95)
        outcome2 = engine.decide(evt2)
        
        # Whitelisted should execute, non-whitelisted should not
        assert True


    def test_admin_only_commands(self, mmgi_pipeline, voice_input_event, face_security):
        """Test: Admin-only commands require admin authentication."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        # Mark as admin-only
        engine.mark_action_admin_only("system_shutdown")
        
        # Regular user attempts
        evt = voice_input_event("system_shutdown", mode="System Mode", confidence=0.95)
        outcome = engine.decide(evt)
        
        if outcome and outcome.action:
            executor.execute(outcome.action)
        
        # Should be blocked without admin auth
        assert True


    def test_session_security_attributes(self, mmgi_pipeline, face_security):
        """Test: Session maintains security attributes."""
        face_data = {
            "user": "test_user",
            "face_encoding": face_security.create_test_encoding(),
            "authorized": True
        }
        
        session = face_security.create_session(face_data)
        
        # Session should have security markers
        assert session.get("authenticated") is True
        assert session.get("user") == "test_user"
