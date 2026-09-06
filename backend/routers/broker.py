"""/broker/* -- connecting a real Kite Connect session.

Kite's login is a human-in-the-loop redirect: the browser visits Kite, Kite
redirects back with a `request_token`, and the backend exchanges that for an
access token that expires daily at ~06:00 IST. All of that already lives in
backend/auth/kite_session.py; these routes are what finally let the Settings
page drive it.

The session is per-deployment, not per-user: there is one set of Kite API
credentials in the environment, so connecting binds this backend to one
broker account. That is the right shape for a personal deployment and the
wrong one for a multi-tenant service -- revisit before this app ever has
users who are not the operator.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependency import get_current_user
from backend.auth.kite_session import KiteSessionManager, KiteSessionState
from backend.auth.models import User
from backend.configs.settings import settings
from backend.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["Broker"])


def get_kite_session() -> KiteSessionManager:
    return KiteSessionManager(settings.KITE_API_KEY, settings.KITE_API_SECRET, db.redis)


class CallbackRequest(BaseModel):
    request_token: str


@router.get("/kite/status")
async def kite_status(
    _user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
):
    state = await session.state()
    return {
        "state": state.value,
        "connected": state == KiteSessionState.ACTIVE,
        # What the Settings card should say to do next.
        "action": {
            KiteSessionState.UNCONFIGURED: "Set KITE_API_KEY and KITE_API_SECRET on the server",
            KiteSessionState.NEEDS_LOGIN: "Connect your Zerodha account",
            KiteSessionState.DEGRADED: "Session expired -- reconnect",
            KiteSessionState.ACTIVE: None,
        }[state],
    }


@router.get("/kite/login-url")
async def kite_login_url(
    _user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
):
    try:
        return {"url": await session.generate_login_url()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/kite/callback")
async def kite_callback(
    body: CallbackRequest,
    _user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
):
    """Kite redirects the browser back with a request_token; the frontend
    hands it here. It is single-use and short-lived, so a failure here means
    "start the login again", not "retry"."""
    try:
        await session.exchange_request_token(body.request_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.warning("kite token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Kite rejected the request token")

    return {"state": (await session.state()).value, "connected": True}


@router.post("/kite/disconnect")
async def kite_disconnect(
    _user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
):
    await session.clear()
    return {"state": (await session.state()).value, "connected": False}
