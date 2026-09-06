"""Smoke test: every non-auth API route defined in server.py rejects an
unauthenticated request. Doesn't exercise route logic (most need Mongo/
external services) -- only proves the auth dependency is actually wired
in, which is exactly the kind of one-line-per-router change that's easy
to silently skip on one entry."""

from fastapi.testclient import TestClient

from backend.server import app

client = TestClient(app)

# One representative path per router mounted in server.py, excluding
# /auth/*, /docs, /redoc, /openapi.json, and the root "/" health message.
PROTECTED_SAMPLE_PATHS = [
    ("GET", "/api/v1/market/indices"),
    ("GET", "/api/v1/watchlist"),
    ("GET", "/api/v1/trading/positions"),
    ("GET", "/api/v1/settings/omniroute-model"),
    ("POST", "/api/v1/agents/analyze/RELIANCE"),
    ("GET", "/api/v1/suggestions"),
    ("GET", "/api/v1/analytics/pnl"),
]


def test_protected_routes_reject_unauthenticated_requests():
    for method, path in PROTECTED_SAMPLE_PATHS:
        resp = client.request(method, path)
        assert resp.status_code in (401, 403), f"{method} {path} returned {resp.status_code}, expected 401/403"


def test_auth_routes_do_not_require_authentication():
    resp = client.post("/api/v1/auth/google", json={"id_token": "whatever-invalid"})
    # 401 here means "invalid Google token" (verified, rejected) -- NOT
    # "missing Authorization header" (which would be 403 from HTTPBearer
    # firing on the wrong route). Either way this must not need a bearer
    # token itself to be reachable.
    assert resp.status_code in (200, 401)
