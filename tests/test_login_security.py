"""
tests/test_login_security.py - Security-focused tests for login hashing.
"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.login_window import (  # noqa: E402
    _hash_pw_bcrypt,
    _verify_password,
    _is_bcrypt_hash,
    _is_strong_face_match,
)


def test_bcrypt_hash_is_not_plaintext():
    password = 'secret-password-123'
    hashed = _hash_pw_bcrypt(password)
    assert hashed != password
    assert _is_bcrypt_hash(hashed)


def test_verify_password_accepts_bcrypt_hash():
    password = 'correct-horse-battery-staple'
    hashed = _hash_pw_bcrypt(password)
    ok, needs_upgrade = _verify_password(password, hashed)
    assert ok is True
    assert needs_upgrade is False


def test_verify_password_rejects_incorrect_password():
    password = 'this-is-right'
    hashed = _hash_pw_bcrypt(password)
    ok, _ = _verify_password('this-is-wrong', hashed)
    assert ok is False


def test_verify_password_legacy_hash_marks_upgrade():
    import hashlib

    password = 'legacy-user-password'
    legacy = hashlib.sha256(password.encode('utf-8')).hexdigest()
    ok, needs_upgrade = _verify_password(password, legacy)
    assert ok is True
    assert needs_upgrade is True


def test_strong_face_match_rejects_none_similarity():
    assert _is_strong_face_match(None, 0.93) is False


def test_strong_face_match_rejects_below_threshold():
    assert _is_strong_face_match(0.91, 0.93) is False


def test_strong_face_match_accepts_threshold_or_higher():
    assert _is_strong_face_match(0.93, 0.93) is True
    assert _is_strong_face_match(0.97, 0.93) is True
