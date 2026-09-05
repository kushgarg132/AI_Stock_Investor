import time

import jwt as pyjwt

from backend.configs.settings import settings


class InvalidSessionToken(Exception):
    pass


def create_session_jwt(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + settings.SESSION_MAX_AGE_SECONDS}
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_session_jwt(token: str) -> str:
    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except pyjwt.PyJWTError as e:
        raise InvalidSessionToken(str(e))
    return payload["sub"]
