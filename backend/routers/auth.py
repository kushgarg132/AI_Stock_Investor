import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependency import get_current_user, get_user_store
from backend.auth.google import verify_google_token, InvalidGoogleToken
from backend.auth.jwt import create_session_jwt
from backend.auth.models import User
from backend.auth.store import UserStore
from backend.database import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


class GoogleLoginRequest(BaseModel):
    id_token: str


class GoogleLoginResponse(BaseModel):
    token: str
    user: User


@router.post("/google", response_model=GoogleLoginResponse)
async def google_login(req: GoogleLoginRequest, user_store: UserStore = Depends(get_user_store)):
    try:
        info = await verify_google_token(req.id_token)
    except InvalidGoogleToken as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    user = await user_store.upsert_from_google(
        google_sub=info.sub, email=info.email, name=info.name, picture=info.picture,
    )
    token = create_session_jwt(user.id)
    logger.info(f"User {user.id} ({user.email}) signed in via Google.")
    return GoogleLoginResponse(token=token, user=user)


@router.post("/logout")
async def logout():
    # Stateless bearer JWT -- no server-side session to invalidate. This
    # endpoint exists for API symmetry; the frontend's actual logout is
    # discarding the locally-stored token.
    return {"message": "Logged out"}


@router.get("/me", response_model=User)
async def get_me(user: User = Depends(get_current_user)):
    return user
