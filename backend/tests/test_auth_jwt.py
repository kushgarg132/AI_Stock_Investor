import time

import pytest

from backend.auth.jwt import create_session_jwt, decode_session_jwt, InvalidSessionToken


def test_create_and_decode_round_trip():
    token = create_session_jwt("user-123")
    assert decode_session_jwt(token) == "user-123"


def test_decode_rejects_tampered_token():
    # Flip a character in the middle of the signature segment, not the
    # last character -- the last base64 char of a segment only carries
    # partial bits, so flipping it can decode to the same underlying bytes
    # some of the time (~1/16), making that choice flaky. A middle
    # character has no such overlap.
    token = create_session_jwt("user-123")
    mid = len(token) // 2
    flipped_char = "A" if token[mid] != "A" else "B"
    tampered = token[:mid] + flipped_char + token[mid + 1:]
    with pytest.raises(InvalidSessionToken):
        decode_session_jwt(tampered)


def test_decode_rejects_expired_token(monkeypatch):
    import backend.auth.jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SESSION_MAX_AGE_SECONDS", 0)
    token = create_session_jwt("user-123")
    time.sleep(1.1)
    with pytest.raises(InvalidSessionToken):
        decode_session_jwt(token)
