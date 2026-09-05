from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt import decode_session_jwt, InvalidSessionToken
from backend.auth.models import User
from backend.auth.store import UserStore
from backend.database import db

_bearer_scheme = HTTPBearer()


async def get_user_store() -> UserStore:
    return UserStore(db.db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    user_store: UserStore = Depends(get_user_store),
) -> User:
    try:
        user_id = decode_session_jwt(credentials.credentials)
    except InvalidSessionToken:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = await user_store.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user
