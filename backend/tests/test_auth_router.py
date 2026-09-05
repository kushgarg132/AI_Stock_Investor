from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.routers import auth as auth_router
from backend.auth.google import GoogleUserInfo
from backend.auth import dependency as auth_dependency
from backend.auth.store import UserStore


def _client(monkeypatch, fake_google_info=None, fake_google_error=None):
    fake_db = AsyncMongoMockClient()["test_db"]
    monkeypatch.setattr(auth_router, "db", type("_Db", (), {"db": fake_db})())
    monkeypatch.setattr(auth_dependency, "db", type("_Db", (), {"db": fake_db})())

    async def fake_verify(token):
        if fake_google_error:
            raise fake_google_error
        return fake_google_info

    monkeypatch.setattr(auth_router, "verify_google_token", fake_verify)

    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api/v1")
    return TestClient(app)


def test_google_login_creates_user_and_returns_token(monkeypatch):
    info = GoogleUserInfo(sub="g1", email="a@example.com", name="Alice", picture="http://pic")
    client = _client(monkeypatch, fake_google_info=info)

    resp = client.post("/api/v1/auth/google", json={"id_token": "whatever"})
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert body["user"]["email"] == "a@example.com"


def test_google_login_rejects_invalid_token(monkeypatch):
    from backend.auth.google import InvalidGoogleToken
    client = _client(monkeypatch, fake_google_error=InvalidGoogleToken("bad token"))

    resp = client.post("/api/v1/auth/google", json={"id_token": "whatever"})
    assert resp.status_code == 401


def test_me_returns_401_without_token(monkeypatch):
    client = _client(monkeypatch)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


def test_me_returns_user_with_valid_token(monkeypatch):
    info = GoogleUserInfo(sub="g2", email="b@example.com", name="Bob", picture=None)
    client = _client(monkeypatch, fake_google_info=info)

    login_resp = client.post("/api/v1/auth/google", json={"id_token": "whatever"})
    token = login_resp.json()["token"]

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "b@example.com"


def test_logout_returns_success_message(monkeypatch):
    client = _client(monkeypatch)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
