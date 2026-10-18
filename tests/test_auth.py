"""
UNIT TESTS for auth.py

These test individual functions in complete isolation — no database,
no FastAPI server, no HTTP requests. They run fast and pinpoint exactly
which piece of logic is broken if something fails.
"""
import pytest
from fastapi import HTTPException
from jose import jwt

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    SECRET_KEY,
    ALGORITHM,
)


def test_hash_password_does_not_store_plain_text():
    """A hashed password should never equal the original plain text —
    this is the whole point of hashing."""
    hashed = hash_password("mypassword123")
    assert hashed != "mypassword123"


def test_hash_password_produces_different_hash_each_time():
    """bcrypt includes a random 'salt', so hashing the SAME password twice
    should still produce two DIFFERENT hashes. This prevents attackers from
    spotting two users who happen to share a password."""
    hash1 = hash_password("samepassword")
    hash2 = hash_password("samepassword")
    assert hash1 != hash2


def test_verify_password_correct_password_returns_true():
    hashed = hash_password("mypassword123")
    assert verify_password("mypassword123", hashed) is True


def test_verify_password_wrong_password_returns_false():
    hashed = hash_password("mypassword123")
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token_contains_correct_claims():
    """The token should embed exactly the username and role we gave it,
    plus an expiry time."""
    token = create_access_token({"sub": "hathi", "role": "admin"})
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert decoded["sub"] == "hathi"
    assert decoded["role"] == "admin"
    assert "exp" in decoded  # expiry timestamp must be present


def test_verify_token_with_valid_token_returns_user_info():
    token = create_access_token({"sub": "hathi", "role": "admin"})
    result = verify_token(token)

    assert result["username"] == "hathi"
    assert result["role"] == "admin"


def test_verify_token_with_garbage_string_raises_401():
    """A completely invalid/malformed token should be rejected with a 401,
    not crash the server with an unhandled exception."""
    with pytest.raises(HTTPException) as exc_info:
        verify_token("this-is-not-a-real-jwt-token")
    assert exc_info.value.status_code == 401


def test_verify_token_with_tampered_token_raises_401():
    """A token signed with the WRONG secret key (as if someone tried to
    forge one) must be rejected."""
    fake_token = jwt.encode(
        {"sub": "hacker", "role": "admin"}, "wrong-secret-key", algorithm=ALGORITHM
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_token(fake_token)
    assert exc_info.value.status_code == 401
