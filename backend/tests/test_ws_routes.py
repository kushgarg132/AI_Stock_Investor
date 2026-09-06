"""The /ws endpoint: authentication, origin, and the subscribe round trip.

A browser cannot set an Authorization header on a WebSocket handshake and
this app keeps its token in localStorage rather than a cookie, so the token
arrives as a query parameter -- which makes the handshake checks the only
thing standing between the socket and an unauthenticated client. CORS
middleware does not cover WebSocket handshakes either, hence the explicit
origin check.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.auth.models import User
from backend.ws import routes as ws_routes
from backend.ws.hub import Hub

_USER = User(
    id="alice", google_sub="sub-1", email="alice@example.com", name="Alice",
    picture=None, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
)

ALLOWED_ORIGIN = "https://app.example.com"


@pytest.fixture
def hub(monkeypatch):
    fresh = Hub()
    monkeypatch.setattr(ws_routes, "hub", fresh)
    return fresh


@pytest.fixture
def client(monkeypatch, hub):
    async def fake_authenticate(token):
        return _USER if token == "good-token" else None

    monkeypatch.setattr(ws_routes, "authenticate_token", fake_authenticate)
    monkeypatch.setattr(ws_routes.settings, "CORS_ALLOWED_ORIGINS", [ALLOWED_ORIGIN])

    app = FastAPI()
    app.include_router(ws_routes.router, prefix="/api/v1")
    return TestClient(app)


def test_a_missing_token_is_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws") as socket:
            socket.receive_json()


def test_an_invalid_token_is_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws?token=nonsense") as socket:
            socket.receive_json()


def test_an_unknown_origin_is_refused(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/v1/ws?token=good-token", headers={"origin": "https://evil.example.com"}
        ) as socket:
            socket.receive_json()


def test_a_valid_token_gets_a_ready_frame(client):
    with client.websocket_connect(
        "/api/v1/ws?token=good-token", headers={"origin": ALLOWED_ORIGIN}
    ) as socket:
        ready = socket.receive_json()
        assert ready["event"] == "ready"
        assert ready["data"]["user_id"] == "alice"


def test_subscribing_then_receiving_a_published_event(client, hub):
    import asyncio

    with client.websocket_connect(
        "/api/v1/ws?token=good-token", headers={"origin": ALLOWED_ORIGIN}
    ) as socket:
        socket.receive_json()  # ready
        socket.send_json({"action": "subscribe", "topics": ["trades"]})
        assert socket.receive_json()["event"] == "subscribed"

        asyncio.run(hub.publish("alice", "trades", "opened", {"symbol": "RELIANCE"}))

        message = socket.receive_json()
        assert message["topic"] == "trades"
        assert message["data"]["symbol"] == "RELIANCE"


def test_a_socket_never_receives_another_users_events(client, hub):
    import asyncio

    with client.websocket_connect(
        "/api/v1/ws?token=good-token", headers={"origin": ALLOWED_ORIGIN}
    ) as socket:
        socket.receive_json()
        socket.send_json({"action": "subscribe", "topics": ["trades"]})
        socket.receive_json()

        asyncio.run(hub.publish("bob", "trades", "opened", {"symbol": "TCS"}))
        asyncio.run(hub.publish("alice", "trades", "opened", {"symbol": "RELIANCE"}))

        message = socket.receive_json()
        assert message["data"]["symbol"] == "RELIANCE", "bob's event must never arrive here"


def test_a_disconnect_removes_the_connection_from_the_hub(client, hub):
    with client.websocket_connect(
        "/api/v1/ws?token=good-token", headers={"origin": ALLOWED_ORIGIN}
    ) as socket:
        socket.receive_json()
        socket.send_json({"action": "subscribe", "topics": ["prices:RELIANCE"]})
        socket.receive_json()

    assert hub.subscribed_symbols() == set()


def test_an_unknown_action_is_reported_not_fatal(client):
    with client.websocket_connect(
        "/api/v1/ws?token=good-token", headers={"origin": ALLOWED_ORIGIN}
    ) as socket:
        socket.receive_json()
        socket.send_json({"action": "teleport"})

        error = socket.receive_json()
        assert error["event"] == "error"

        socket.send_json({"action": "subscribe", "topics": ["pnl"]})
        assert socket.receive_json()["event"] == "subscribed", "socket stays usable"
