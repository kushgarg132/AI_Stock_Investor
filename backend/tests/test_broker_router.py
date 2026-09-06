"""/broker/kite/* -- the Settings card's view of the Kite session.

KiteSessionManager itself is already covered; what matters here is that the
routes report a state the UI can act on and never leak a broker token to the
client.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependency import get_current_user
from backend.auth.kite_session import KiteSessionState
from backend.auth.models import User
from backend.routers import broker

_USER = User(
    id="alice", google_sub="sub-1", email="alice@example.com", name="Alice",
    picture=None, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
)


class _FakeSession:
    def __init__(self, state=KiteSessionState.NEEDS_LOGIN, fail_exchange=False):
        self._state = state
        self.fail_exchange = fail_exchange
        self.cleared = False
        self.exchanged = None

    async def state(self):
        return self._state

    async def generate_login_url(self):
        if self._state == KiteSessionState.UNCONFIGURED:
            raise RuntimeError("KITE_API_KEY is not configured")
        return "https://kite.zerodha.com/connect/login?api_key=abc&v=3"

    async def exchange_request_token(self, request_token):
        if self.fail_exchange:
            raise Exception("token expired")
        self.exchanged = request_token
        self._state = KiteSessionState.ACTIVE
        return "access-token-value"

    async def clear(self):
        self.cleared = True
        self._state = KiteSessionState.NEEDS_LOGIN


def _client(session):
    app = FastAPI()
    app.include_router(broker.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[broker.get_kite_session] = lambda: session
    return TestClient(app)


def test_status_tells_the_ui_what_to_do_next():
    resp = _client(_FakeSession()).get("/api/v1/broker/kite/status")

    assert resp.status_code == 200
    assert resp.json() == {
        "state": "NEEDS_LOGIN", "connected": False, "action": "Connect your Zerodha account",
    }


def test_an_active_session_needs_no_action():
    resp = _client(_FakeSession(KiteSessionState.ACTIVE)).get("/api/v1/broker/kite/status")

    assert resp.json()["connected"] is True
    assert resp.json()["action"] is None


def test_login_url_is_returned_for_the_human_to_visit():
    resp = _client(_FakeSession()).get("/api/v1/broker/kite/login-url")

    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://kite.zerodha.com/connect/login")


def test_login_url_without_credentials_is_a_client_error():
    resp = _client(_FakeSession(KiteSessionState.UNCONFIGURED)).get("/api/v1/broker/kite/login-url")

    assert resp.status_code == 400
    assert "KITE_API_KEY" in resp.json()["detail"]


def test_callback_exchanges_the_request_token():
    session = _FakeSession()

    resp = _client(session).post("/api/v1/broker/kite/callback", json={"request_token": "rt-123"})

    assert resp.status_code == 200
    assert resp.json() == {"state": "ACTIVE", "connected": True}
    assert session.exchanged == "rt-123"


def test_callback_never_returns_the_access_token():
    """The browser has no use for a broker token and every reason not to
    hold one."""
    resp = _client(_FakeSession()).post("/api/v1/broker/kite/callback", json={"request_token": "rt-123"})

    assert "access-token-value" not in resp.text


def test_a_rejected_request_token_is_reported_as_a_gateway_failure():
    resp = _client(_FakeSession(fail_exchange=True)).post(
        "/api/v1/broker/kite/callback", json={"request_token": "stale"}
    )

    assert resp.status_code == 502


def test_disconnect_forgets_the_cached_token():
    session = _FakeSession(KiteSessionState.ACTIVE)

    resp = _client(session).post("/api/v1/broker/kite/disconnect")

    assert resp.json() == {"state": "NEEDS_LOGIN", "connected": False}
    assert session.cleared is True
