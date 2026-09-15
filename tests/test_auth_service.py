import time

import jwt
import pytest

from app.auth.service import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.config import get_settings


def test_hash_password_does_not_store_plaintext():
    hashed = hash_password("correct-password")
    assert hashed != "correct-password"
    assert "correct-password" not in hashed


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct-password")
    assert verify_password("correct-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_is_salted_not_deterministic():
    # Same input, two independent hashes, must differ — otherwise two users with
    # the same password would have identical hashed_password rows, leaking that
    # fact to anyone with database access.
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first) is True
    assert verify_password("same-password", second) is True


def test_create_and_decode_access_token_roundtrips():
    token = create_access_token("alice")
    assert decode_access_token(token) == "alice"


def test_decode_access_token_rejects_tampered_signature():
    token = create_access_token("alice")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_decode_access_token_rejects_expired_token():
    # Builds an already-expired token directly (bypassing create_access_token's
    # fixed expiry window) rather than sleeping through the real expiry duration,
    # so this test runs in milliseconds, not an hour.
    settings = get_settings()
    payload = {"sub": "alice", "exp": time.time() - 10}
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_decode_access_token_rejects_wrong_secret():
    payload = {"sub": "alice", "exp": time.time() + 60}
    # >=32 bytes specifically to avoid PyJWT's own InsecureKeyLengthWarning for
    # HS256 (RFC 7518 Section 3.2) — this key's only job is to differ from the
    # real one, its insecurity as a real secret isn't what's under test here.
    token = jwt.encode(payload, "a-different-secret-thats-32-bytes-long", algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
