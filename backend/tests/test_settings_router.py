import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import settings as settings_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(settings_router.router, prefix="/api/v1")
    return TestClient(app)


class _FakeModelsResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"data": [
            {"id": "antigravity/gemini-2.5-flash", "owned_by": "antigravity"},
            {"id": "aug/sonnet5-high", "owned_by": "aug"},
        ]}


def test_list_omniroute_models_returns_stripped_ids(client, monkeypatch):
    async def fake_get(self, url, **kwargs):
        return _FakeModelsResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    resp = client.get("/api/v1/settings/omniroute-models")
    assert resp.status_code == 200
    assert resp.json() == [
        {"id": "antigravity/gemini-2.5-flash"},
        {"id": "aug/sonnet5-high"},
    ]


def test_list_omniroute_models_returns_502_on_gateway_error(client, monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    resp = client.get("/api/v1/settings/omniroute-models")
    assert resp.status_code == 502


def test_get_omniroute_model_returns_current_setting(client):
    resp = client.get("/api/v1/settings/omniroute-model")
    assert resp.status_code == 200
    assert "model" in resp.json()


def test_set_omniroute_model_persists_to_env_file(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_VAR=1\nOMNIROUTE_MODEL=old-model\n")
    monkeypatch.setattr(settings_router, "ENV_PATH", env_file)

    resp = client.post("/api/v1/settings/omniroute-model", json={"model": "aug/sonnet5-high"})
    assert resp.status_code == 200

    updated = env_file.read_text()
    assert "OMNIROUTE_MODEL=aug/sonnet5-high" in updated
    assert "SOME_OTHER_VAR=1" in updated

    resp2 = client.get("/api/v1/settings/omniroute-model")
    assert resp2.json()["model"] == "aug/sonnet5-high"


def test_set_omniroute_model_rejects_empty(client):
    resp = client.post("/api/v1/settings/omniroute-model", json={"model": "   "})
    assert resp.status_code == 400
