import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from backend.auth.dependency import get_current_user, get_user_store
from backend.auth.google import verify_google_token, InvalidGoogleToken
from backend.auth.jwt import create_session_jwt
from backend.auth.models import User
from backend.auth.refresh_store import RefreshTokenStore
from backend.auth.store import UserStore
from backend.configs.settings import settings
from backend.database import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def get_refresh_store() -> RefreshTokenStore:
    return RefreshTokenStore(db.db)


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    # Scoped to /api/v1/auth: the browser only ever needs to present this
    # cookie to /auth/refresh and /auth/logout, so it never rides along on
    # every other API call. SameSite=None + Secure is required for it to
    # survive the frontend (Vercel) -> backend (nip.io) cross-site request;
    # the backend's own CORS allow_origins is an explicit list, never "*",
    # which is what makes a credentialed cross-origin cookie legal at all.
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_MAX_AGE_SECONDS,
        path="/api/v1/auth",
        httponly=True,
        secure=True,
        samesite="none",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME, path="/api/v1/auth", secure=True, samesite="none",
    )


class GoogleLoginRequest(BaseModel):
    id_token: str


class GoogleLoginResponse(BaseModel):
    token: str
    user: User


class RefreshResponse(BaseModel):
    token: str


@router.post("/google", response_model=GoogleLoginResponse)
async def google_login(
    req: GoogleLoginRequest,
    response: Response,
    user_store: UserStore = Depends(get_user_store),
    refresh_store: RefreshTokenStore = Depends(get_refresh_store),
):
    try:
        info = await verify_google_token(req.id_token)
    except InvalidGoogleToken as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    user = await user_store.upsert_from_google(
        google_sub=info.sub, email=info.email, name=info.name, picture=info.picture,
    )
    token = create_session_jwt(user.id)
    raw_refresh = await refresh_store.issue(user.id)
    _set_refresh_cookie(response, raw_refresh)
    logger.info(f"User {user.id} ({user.email}) signed in via Google.")
    return GoogleLoginResponse(token=token, user=user)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_store: RefreshTokenStore = Depends(get_refresh_store),
):
    """No get_current_user dependency here on purpose: by the time the
    access token needs refreshing, it may already be expired -- the whole
    point of this endpoint is to work from the refresh cookie alone."""
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=401, detail="No refresh session")

    result = await refresh_store.rotate(raw)
    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh session expired or revoked")

    user_id, new_raw = result
    _set_refresh_cookie(response, new_raw)
    return RefreshResponse(token=create_session_jwt(user_id))


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    refresh_store: RefreshTokenStore = Depends(get_refresh_store),
):
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if raw:
        await refresh_store.revoke(raw)
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=User)
async def get_me(user: User = Depends(get_current_user)):
    return user
