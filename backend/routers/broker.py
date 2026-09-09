"""/broker/* -- connecting a real Kite Connect session.

Kite's login is a human-in-the-loop redirect: the browser visits Kite, Kite
redirects back with a `request_token`, and the backend exchanges that for an
access token that expires daily at ~06:00 IST. All of that already lives in
backend/auth/kite_session.py; these routes are what finally let the Settings
page drive it.

Everything here is per-user: the caller's own API key and secret come from the
encrypted credential store, and the resulting access token is cached under a
key scoped to them. Connecting binds *that user* to their own broker account,
never the deployment to one shared account.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.broker_credentials import BrokerCredentialStore, get_credential_store
from backend.auth.dependency import get_current_user
from backend.auth.kite_session import KiteSessionManager, KiteSessionState
from backend.auth.models import User
from backend.database import db
from backend.instruments.loader import refresh_instruments_from_kite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["Broker"])


async def get_kite_session(
    user: User = Depends(get_current_user),
    credentials: BrokerCredentialStore = Depends(get_credential_store),
) -> KiteSessionManager:
    creds = await credentials.get(user.id, "kite")
    return KiteSessionManager(
        api_key=creds.api_key if creds else None,
        api_secret=creds.api_secret if creds else None,
        redis=db.redis,
        user_id=user.id,
    )


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
            KiteSessionState.UNCONFIGURED: "Add your Kite API key and secret in Settings",
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
    user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
    credentials: BrokerCredentialStore = Depends(get_credential_store),
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

    # Best-effort, off the response: this is what actually expands the
    # instrument master beyond the bundled ~130-symbol seed (see loader.py) --
    # do it the moment a session connects rather than making the operator
    # wait for the next backend restart. The instrument master is shared
    # reference data, so any connected user's session can refresh it.
    creds = await credentials.get(user.id, "kite")
    kite_count = await refresh_instruments_from_kite(session, creds.api_key) if creds else 0
    if kite_count:
        logger.info(f"Instrument master expanded from Kite: {kite_count} upserted.")

    return {"state": (await session.state()).value, "connected": True}


@router.post("/kite/disconnect")
async def kite_disconnect(
    _user: User = Depends(get_current_user),
    session: KiteSessionManager = Depends(get_kite_session),
):
    await session.clear()
    return {"state": (await session.state()).value, "connected": False}
