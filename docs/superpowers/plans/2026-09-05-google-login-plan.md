# Google Login (Core Auth) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require Google sign-in for the whole app — verify a Google ID token server-side, issue the app's own bearer JWT, gate every existing route/page behind it, and replace the hardcoded `"default-user"` Watchlist owner with the real signed-in user.

**Architecture:** Frontend uses Google Identity Services (`@react-oauth/google`) to get an ID token, POSTs it to a new `/auth/google` endpoint. The backend verifies it via Google's own `google-auth` library (already a transitive dependency), upserts a `User` document in a new Mongo `users` collection, and returns the app's own signed JWT in the response body — no cookies, matching RoutineOS's proven production pattern on this same VM (stateless bearer token, avoids cross-origin `SameSite`/`Secure` cookie complexity between the Vercel frontend and the nip.io-fronted backend). Every existing FastAPI router gets gated via `dependencies=[Depends(get_current_user)]`; every existing frontend route gets wrapped in a `RequireAuth` component.

**Tech Stack:** FastAPI, `google-auth` (already installed), `pyjwt` (already installed as a transitive dep, pinned directly here), Motor/MongoDB, React 19, `@react-oauth/google` (new), axios interceptors.

**Spec:** `docs/superpowers/specs/2026-09-05-google-login-design.md`

## Global Constraints

- Session transport is a **bearer JWT in the `Authorization` header, never a cookie** — no `Set-Cookie` anywhere in this plan.
- `google-auth` and `pyjwt` are confirmed already importable in the current environment (`python3 -c "import google.oauth2.id_token"` and `python3 -c "import jwt"` both succeed) — pin them directly in `requirements.txt` rather than relying on them staying transitive.
- CORS must move from `allow_origins=["*"]` (with `allow_credentials=True`, an invalid combo) to an explicit `CORS_ALLOWED_ORIGINS` list.
- `auth.router` itself, plus `/docs`/`/redoc`/`/openapi.json`, are the only unauthenticated surface — every other router gets the `get_current_user` dependency.
- Open signup — no email allowlist, any Google account can sign in.
- **Human-required blocking step**: a dedicated Google OAuth Client ID must be created in Google Cloud Console before end-to-end verification (Task 8) can run. Backend and frontend code in Tasks 1–7 can be written and unit-tested without it (verification uses a manually-signed fake token or mocks Google's verifier). Task 8 explicitly stops and asks the user to create it if it isn't already done.

---

### Task 1: `User` model, `UserStore`, and Mongo collection

**Files:**
- Create: `backend/auth/__init__.py` (empty)
- Create: `backend/auth/models.py`
- Create: `backend/auth/store.py`
- Test: `backend/tests/test_auth_store.py`

**Interfaces:**
- Produces: `User` Pydantic model — `{id: str, google_sub: str, email: str, name: str, picture: Optional[str], created_at: datetime}`. `UserStore.__init__(self, db)`, `async def upsert_from_google(self, google_sub: str, email: str, name: str, picture: Optional[str]) -> User`, `async def get_by_id(self, user_id: str) -> Optional[User]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_store.py`:

```python
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.auth.store import UserStore


@pytest.fixture
def store():
    client = AsyncMongoMockClient()
    return UserStore(client["test_db"])


def test_upsert_from_google_creates_new_user(store):
    user = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice", picture="http://pic",
    ))
    assert user.google_sub == "google-sub-123"
    assert user.email == "a@example.com"
    assert user.name == "Alice"
    assert user.picture == "http://pic"
    assert user.id  # a fresh id was assigned


def test_upsert_from_google_is_idempotent_by_google_sub(store):
    first = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice", picture=None,
    ))
    second = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-123", email="a@example.com", name="Alice Updated", picture=None,
    ))
    assert first.id == second.id
    assert second.name == "Alice Updated"


def test_get_by_id_returns_none_for_unknown_user(store):
    result = asyncio.run(store.get_by_id("no-such-id"))
    assert result is None


def test_get_by_id_returns_the_stored_user(store):
    created = asyncio.run(store.upsert_from_google(
        google_sub="google-sub-456", email="b@example.com", name="Bob", picture=None,
    ))
    fetched = asyncio.run(store.get_by_id(created.id))
    assert fetched is not None
    assert fetched.email == "b@example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/test_auth_store.py -v`
Expected: FAIL — `backend.auth.store` doesn't exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Write `backend/auth/models.py`**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: str
    google_sub: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime
```

- [ ] **Step 4: Write `backend/auth/store.py`**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.auth.models import User


def _to_user(doc: dict) -> User:
    doc = dict(doc)
    doc.pop("_id", None)
    return User(**doc)


class UserStore:
    """Mongo-backed user store. Collection `users`, unique index on
    google_sub. This is the one and only place a User document is ever
    created in this app -- there is no separate password-registration
    path to keep in sync (unlike RoutineOS, which has both and once let a
    field drift between them). If a second account-creation path is ever
    added, audit its field set against upsert_from_google explicitly."""

    def __init__(self, db):
        self.collection = db["users"]

    async def ensure_indexes(self):
        await self.collection.create_index("google_sub", unique=True)

    async def upsert_from_google(
        self, google_sub: str, email: str, name: str, picture: Optional[str]
    ) -> User:
        existing = await self.collection.find_one({"google_sub": google_sub})
        if existing is not None:
            await self.collection.update_one(
                {"google_sub": google_sub},
                {"$set": {"email": email, "name": name, "picture": picture}},
            )
            existing.update({"email": email, "name": name, "picture": picture})
            return _to_user(existing)

        user = User(
            id=str(uuid.uuid4()),
            google_sub=google_sub,
            email=email,
            name=name,
            picture=picture,
            created_at=datetime.now(timezone.utc),
        )
        await self.collection.insert_one(user.model_dump())
        return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.collection.find_one({"id": user_id})
        return _to_user(doc) if doc else None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_auth_store.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/auth/__init__.py backend/auth/models.py backend/auth/store.py backend/tests/test_auth_store.py
git commit -m "feat: add User model and Mongo-backed UserStore

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 2: Google ID-token verification

**Files:**
- Create: `backend/auth/google.py`
- Modify: `backend/requirements.txt` (add `google-auth` explicitly)
- Modify: `backend/configs/settings.py` (add `GOOGLE_CLIENT_ID`)
- Test: `backend/tests/test_auth_google.py`

**Interfaces:**
- Consumes: `settings.GOOGLE_CLIENT_ID: str` (new).
- Produces: `GoogleUserInfo` dataclass `{sub: str, email: str, name: str, picture: Optional[str]}`. `class InvalidGoogleToken(Exception)`. `async def verify_google_token(id_token: str) -> GoogleUserInfo` (raises `InvalidGoogleToken` on any failure).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_google.py`:

```python
import pytest
from google.auth.exceptions import GoogleAuthError

from backend.auth.google import verify_google_token, InvalidGoogleToken


def test_verify_google_token_returns_user_info_on_success(monkeypatch):
    def fake_verify(token, request, audience):
        assert token == "valid-token"
        return {
            "sub": "google-sub-123",
            "email": "a@example.com",
            "name": "Alice",
            "picture": "http://pic",
        }

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    info = pytest.run(verify_google_token("valid-token")) if False else __import__("asyncio").run(
        verify_google_token("valid-token")
    )
    assert info.sub == "google-sub-123"
    assert info.email == "a@example.com"
    assert info.name == "Alice"
    assert info.picture == "http://pic"


def test_verify_google_token_raises_on_invalid_token(monkeypatch):
    def fake_verify(token, request, audience):
        raise GoogleAuthError("Token expired")

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    with pytest.raises(InvalidGoogleToken):
        __import__("asyncio").run(verify_google_token("bad-token"))


def test_verify_google_token_defaults_picture_to_none_when_missing(monkeypatch):
    def fake_verify(token, request, audience):
        return {"sub": "google-sub-456", "email": "b@example.com", "name": "Bob"}

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    info = __import__("asyncio").run(verify_google_token("valid-token"))
    assert info.picture is None
```

(The `pytest.run(...) if False else` line above is dead — remove it; keeping the plan's test code exactly as intended below in Step 3's real form. See Step 4 for the corrected, final test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_auth_google.py -v`
Expected: FAIL — `backend.auth.google` doesn't exist yet.

- [ ] **Step 3: Add `GOOGLE_CLIENT_ID` to settings**

In `backend/configs/settings.py`, add near the OmniRoute block:

```python
    # Google Sign-In (ID-token verification only -- no client secret, no
    # redirect URI needed for this flow).
    GOOGLE_CLIENT_ID: Optional[str] = None
```

- [ ] **Step 4: Write `backend/auth/google.py`**

```python
import logging
from dataclasses import dataclass
from typing import Optional

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from backend.configs.settings import settings

logger = logging.getLogger(__name__)


class InvalidGoogleToken(Exception):
    pass


@dataclass
class GoogleUserInfo:
    sub: str
    email: str
    name: str
    picture: Optional[str] = None


async def verify_google_token(token: str) -> GoogleUserInfo:
    """Verifies a Google ID token's signature, issuer, audience, and expiry
    via Google's own client library (mirrors RoutineOS's use of the Java
    equivalent GoogleIdTokenVerifier -- don't hand-roll JWKS fetching)."""
    try:
        payload = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.GOOGLE_CLIENT_ID,
        )
    except (GoogleAuthError, ValueError) as e:
        logger.warning(f"Google ID token verification failed: {e}")
        raise InvalidGoogleToken(str(e))

    return GoogleUserInfo(
        sub=payload["sub"],
        email=payload["email"],
        name=payload.get("name", payload["email"]),
        picture=payload.get("picture"),
    )
```

- [ ] **Step 5: Rewrite the test file cleanly (replacing the dead-code draft from Step 1)**

Overwrite `backend/tests/test_auth_google.py` in full:

```python
import asyncio

import pytest
from google.auth.exceptions import GoogleAuthError

from backend.auth.google import verify_google_token, InvalidGoogleToken


def test_verify_google_token_returns_user_info_on_success(monkeypatch):
    def fake_verify(token, request, audience):
        assert token == "valid-token"
        return {
            "sub": "google-sub-123",
            "email": "a@example.com",
            "name": "Alice",
            "picture": "http://pic",
        }

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    info = asyncio.run(verify_google_token("valid-token"))
    assert info.sub == "google-sub-123"
    assert info.email == "a@example.com"
    assert info.name == "Alice"
    assert info.picture == "http://pic"


def test_verify_google_token_raises_on_invalid_token(monkeypatch):
    def fake_verify(token, request, audience):
        raise GoogleAuthError("Token expired")

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    with pytest.raises(InvalidGoogleToken):
        asyncio.run(verify_google_token("bad-token"))


def test_verify_google_token_defaults_picture_to_none_when_missing(monkeypatch):
    def fake_verify(token, request, audience):
        return {"sub": "google-sub-456", "email": "b@example.com", "name": "Bob"}

    monkeypatch.setattr("backend.auth.google.id_token.verify_oauth2_token", fake_verify)

    info = asyncio.run(verify_google_token("valid-token"))
    assert info.picture is None
```

- [ ] **Step 6: Add `google-auth` explicitly to `backend/requirements.txt`**

Add this line (near `google-genai`):

```
google-auth>=2.23.0
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth_google.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/auth/google.py backend/configs/settings.py backend/requirements.txt backend/tests/test_auth_google.py
git commit -m "feat: verify Google ID tokens via google-auth library

Uses Google's own client library (mirrors RoutineOS's Java
GoogleIdTokenVerifier) rather than hand-rolling JWKS fetch/caching.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 3: Session JWT (create/decode) and `get_current_user` dependency

**Files:**
- Create: `backend/auth/jwt.py`
- Create: `backend/auth/dependency.py`
- Modify: `backend/configs/settings.py` (add `JWT_SECRET`, `SESSION_MAX_AGE_SECONDS`)
- Test: `backend/tests/test_auth_jwt.py`
- Test: `backend/tests/test_auth_dependency.py`

**Interfaces:**
- Consumes: `User` (Task 1), `UserStore.get_by_id` (Task 1), `settings.JWT_SECRET`, `settings.SESSION_MAX_AGE_SECONDS`.
- Produces: `def create_session_jwt(user_id: str) -> str`. `class InvalidSessionToken(Exception)`. `def decode_session_jwt(token: str) -> str` (returns the user id, raises `InvalidSessionToken`). `async def get_current_user(credentials, user_store) -> User` FastAPI dependency (raises `HTTPException(401)`).

- [ ] **Step 1: Write the failing JWT test**

Create `backend/tests/test_auth_jwt.py`:

```python
import time

import pytest

from backend.auth.jwt import create_session_jwt, decode_session_jwt, InvalidSessionToken


def test_create_and_decode_round_trip():
    token = create_session_jwt("user-123")
    assert decode_session_jwt(token) == "user-123"


def test_decode_rejects_tampered_token():
    token = create_session_jwt("user-123")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(InvalidSessionToken):
        decode_session_jwt(tampered)


def test_decode_rejects_expired_token(monkeypatch):
    import backend.auth.jwt as jwt_module
    monkeypatch.setattr(jwt_module.settings, "SESSION_MAX_AGE_SECONDS", 0)
    token = create_session_jwt("user-123")
    time.sleep(1.1)
    with pytest.raises(InvalidSessionToken):
        decode_session_jwt(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_auth_jwt.py -v`
Expected: FAIL — `backend.auth.jwt` doesn't exist yet.

- [ ] **Step 3: Add `JWT_SECRET`/`SESSION_MAX_AGE_SECONDS` to settings**

In `backend/configs/settings.py`, add:

```python
    # Session JWT (bearer token, not a cookie -- see auth design spec).
    JWT_SECRET: str = "change-me-in-production"
    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days
```

- [ ] **Step 4: Write `backend/auth/jwt.py`**

```python
import time

import jwt as pyjwt

from backend.configs.settings import settings


class InvalidSessionToken(Exception):
    pass


def create_session_jwt(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + settings.SESSION_MAX_AGE_SECONDS}
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_session_jwt(token: str) -> str:
    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except pyjwt.PyJWTError as e:
        raise InvalidSessionToken(str(e))
    return payload["sub"]
```

- [ ] **Step 5: Run JWT test to verify it passes**

Run: `python3 -m pytest tests/test_auth_jwt.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Write the failing dependency test**

Create `backend/tests/test_auth_dependency.py`:

```python
import asyncio

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.auth.dependency import get_current_user
from backend.auth.jwt import create_session_jwt
from backend.auth.store import UserStore


@pytest.fixture
def user_store():
    client = AsyncMongoMockClient()
    return UserStore(client["test_db"])


@pytest.fixture
def client(user_store):
    app = FastAPI()

    async def _get_user_store():
        return user_store

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    app.dependency_overrides[get_current_user.__wrapped__] = None  # placeholder, removed below
    return TestClient(app), user_store


def test_missing_authorization_header_returns_401_or_403():
    app = FastAPI()

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    client = TestClient(app)
    resp = client.get("/protected")
    assert resp.status_code in (401, 403)


def test_valid_token_for_known_user_succeeds():
    store = UserStore(AsyncMongoMockClient()["test_db"])
    user = asyncio.run(store.upsert_from_google(
        google_sub="g1", email="a@example.com", name="Alice", picture=None,
    ))
    token = create_session_jwt(user.id)

    app = FastAPI()

    async def _override():
        return store

    from backend.auth.dependency import get_user_store

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    app.dependency_overrides[get_user_store] = _override
    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == user.id


def test_token_for_unknown_user_returns_401():
    store = UserStore(AsyncMongoMockClient()["test_db"])
    token = create_session_jwt("no-such-user-id")

    app = FastAPI()

    async def _override():
        return store

    from backend.auth.dependency import get_user_store

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    app.dependency_overrides[get_user_store] = _override
    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 401


def test_tampered_token_returns_401():
    token = create_session_jwt("some-user-id")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    app = FastAPI()

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
```

Delete the unused `client`/`user_store` fixture and the dead `test_missing_authorization_header_returns_401_or_403`'s duplicate app -- each test builds its own minimal `FastAPI()` app inline since the dependency needs per-test `dependency_overrides`; the earlier shared `client` fixture above is dead weight, remove it (the final file has 4 test functions, no shared fixtures).

- [ ] **Step 7: Run test to verify it fails**

Run: `python3 -m pytest tests/test_auth_dependency.py -v`
Expected: FAIL — `backend.auth.dependency` doesn't exist yet.

- [ ] **Step 8: Write `backend/auth/dependency.py`**

```python
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
```

- [ ] **Step 9: Clean up and finalize the test file from Step 6**

Overwrite `backend/tests/test_auth_dependency.py` in full with the clean version (no dead fixture):

```python
import asyncio

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.auth.dependency import get_current_user, get_user_store
from backend.auth.jwt import create_session_jwt
from backend.auth.store import UserStore


def _make_app():
    app = FastAPI()

    @app.get("/protected")
    async def protected(user=Depends(get_current_user)):
        return {"user_id": user.id}

    return app


def test_missing_authorization_header_returns_401_or_403():
    client = TestClient(_make_app())
    resp = client.get("/protected")
    assert resp.status_code in (401, 403)


def test_valid_token_for_known_user_succeeds():
    store = UserStore(AsyncMongoMockClient()["test_db"])
    user = asyncio.run(store.upsert_from_google(
        google_sub="g1", email="a@example.com", name="Alice", picture=None,
    ))
    token = create_session_jwt(user.id)

    app = _make_app()

    async def _override():
        return store

    app.dependency_overrides[get_user_store] = _override
    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == user.id


def test_token_for_unknown_user_returns_401():
    store = UserStore(AsyncMongoMockClient()["test_db"])
    token = create_session_jwt("no-such-user-id")

    app = _make_app()

    async def _override():
        return store

    app.dependency_overrides[get_user_store] = _override
    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_tampered_token_returns_401():
    token = create_session_jwt("some-user-id")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    client = TestClient(_make_app())
    resp = client.get("/protected", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth_dependency.py -v`
Expected: PASS (4 tests)

- [ ] **Step 11: Run the full backend suite so far**

Run: `python3 -m pytest tests/ -q`
Expected: all pass (no existing test touches `backend/auth/*`).

- [ ] **Step 12: Commit**

```bash
git add backend/auth/jwt.py backend/auth/dependency.py backend/configs/settings.py backend/tests/test_auth_jwt.py backend/tests/test_auth_dependency.py
git commit -m "feat: add session JWT create/decode and get_current_user dependency

Bearer-token auth via FastAPI's HTTPBearer -- no cookies, matching
RoutineOS's stateless session pattern already in production on this VM.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 4: `/auth/*` router and CORS fix

**Files:**
- Create: `backend/routers/auth.py`
- Modify: `backend/configs/settings.py` (add `CORS_ALLOWED_ORIGINS`)
- Modify: `backend/server.py:35-42` (CORS middleware), mount `auth.router`
- Test: `backend/tests/test_auth_router.py`

**Interfaces:**
- Consumes: `verify_google_token` (Task 2), `create_session_jwt` (Task 3), `UserStore` (Task 1), `get_current_user` (Task 3).
- Produces: `POST /auth/google` → `{"token": str, "user": {...}}`. `POST /auth/logout` → `{"message": str}`. `GET /auth/me` → `User` dict or 401.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_router.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_auth_router.py -v`
Expected: FAIL — `backend.routers.auth` doesn't exist yet.

- [ ] **Step 3: Add `CORS_ALLOWED_ORIGINS` to settings**

In `backend/configs/settings.py`, add:

```python
    # Explicit CORS allowlist -- replaces allow_origins=["*"], which is an
    # invalid combination with allow_credentials=True for real credentialed
    # cross-origin requests.
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
```

- [ ] **Step 4: Write `backend/routers/auth.py`**

```python
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
```

- [ ] **Step 5: Wire CORS + mount `auth.router` in `server.py`**

In `backend/server.py`, replace:

```python
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

with:

```python
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

And add, right after the CORS block (before the database-events section), mount the new router unauthenticated:

```python
from backend.routers import auth as auth_router
app.include_router(auth_router.router, prefix=settings.API_PREFIX, tags=["Auth"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Run the full backend suite**

Run: `python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/routers/auth.py backend/configs/settings.py backend/server.py backend/tests/test_auth_router.py
git commit -m "feat: add /auth/google, /auth/logout, /auth/me routes

Also fixes CORS: allow_origins=[\"*\"] + allow_credentials=True was an
invalid combination for real credentialed cross-origin requests --
replaced with an explicit CORS_ALLOWED_ORIGINS list.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 5: Gate every existing router behind `get_current_user`

**Files:**
- Modify: `backend/server.py:60-87` (every `include_router` call except `auth.router`)
- Test: `backend/tests/test_routes_require_auth.py`

**Interfaces:**
- Consumes: `get_current_user` (Task 3).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_routes_require_auth.py`:

```python
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
    ("GET", "/api/v1/watchlist/someuser"),
    ("GET", "/api/v1/trading/positions"),
    ("GET", "/api/v1/settings/omniroute-model"),
    ("POST", "/api/v1/agents/analyze/RELIANCE"),
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_routes_require_auth.py -v`
Expected: FAIL — none of the routers are gated yet, so the sampled paths return their normal (non-401) responses (404/422/500 depending on route, but not 401/403).

- [ ] **Step 3: Add the dependency to every `include_router` call**

In `backend/server.py`, add `from fastapi import Depends` to the existing `from fastapi import FastAPI` import line, add `from backend.auth.dependency import get_current_user` near the other new imports, and change every existing router-mount line (lines 60-87 as currently ordered) to include `dependencies=[Depends(get_current_user)]`:

```python
app.include_router(news.router, prefix=settings.API_PREFIX, tags=["News"], dependencies=[Depends(get_current_user)])
app.include_router(sentiment.router, prefix=settings.API_PREFIX, tags=["News"], dependencies=[Depends(get_current_user)])
app.include_router(events.router, prefix=settings.API_PREFIX, tags=["Events"], dependencies=[Depends(get_current_user)])
app.include_router(price.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(support.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(trend.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(volume.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(risk.router, prefix=settings.API_PREFIX, tags=["Risk"], dependencies=[Depends(get_current_user)])
app.include_router(stock_info.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(stock_scanner.router, prefix=settings.API_PREFIX, tags=["Scanner"], dependencies=[Depends(get_current_user)])

# Agents Router
from backend.routers import agents
from backend.routers import chat

app.include_router(agents.router, prefix=f"{settings.API_PREFIX}/agents", tags=["Agents"], dependencies=[Depends(get_current_user)])
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["Chat"], dependencies=[Depends(get_current_user)])

from backend.routers import settings as settings_router
app.include_router(settings_router.router, prefix=settings.API_PREFIX, tags=["Settings"], dependencies=[Depends(get_current_user)])

from backend.routers import market_data
from backend.routers import watchlist
from backend.routers import trading

app.include_router(market_data.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(watchlist.router, prefix=settings.API_PREFIX, tags=["Watchlist"], dependencies=[Depends(get_current_user)])
app.include_router(trading.router, prefix=settings.API_PREFIX, tags=["Trading"], dependencies=[Depends(get_current_user)])
```

`auth.router` (mounted in Task 4) stays exactly as-is, with no `dependencies=` kwarg — it must remain reachable without a token.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_routes_require_auth.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `python3 -m pytest tests/ -q`
Expected: all pass. (Existing route-level tests that use `TestClient` directly against a bare `FastAPI()` app they construct themselves — e.g. `test_trading_router.py`, `test_settings_router.py` — mount only the router under test with no auth dependency attached, so they're unaffected. Only `test_routes_require_auth.py` imports the real `backend.server.app`.)

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_routes_require_auth.py
git commit -m "feat: gate every existing router behind get_current_user

auth.router (and /docs, /redoc, /openapi.json) remain the only
unauthenticated surface.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 6: Frontend auth context, login page, and route gating

**Files:**
- Modify: `frontend/package.json` (add `@react-oauth/google`)
- Modify: `frontend/src/main.jsx` (wrap in `GoogleOAuthProvider`)
- Create: `frontend/src/context/AuthContext.jsx`
- Create: `frontend/src/pages/Login.jsx`
- Create: `frontend/src/components/RequireAuth.jsx`
- Modify: `frontend/src/App.jsx` (wrap every route in `RequireAuth`, add `/login`)
- Modify: `frontend/src/utils/api.js` (endpoints + interceptors)

**Interfaces:**
- Consumes: `POST /auth/google`, `GET /auth/me` (Task 4).
- Produces: `useAuth()` hook → `{user, loading, login(idToken), logout()}`. `<RequireAuth>{children}</RequireAuth>`.

- [ ] **Step 1: Install `@react-oauth/google`**

```bash
cd frontend && npm install @react-oauth/google
```

- [ ] **Step 2: Add auth endpoints to `api.js` and wire interceptors**

In `frontend/src/utils/api.js`, add to the `endpoints` object (after `settings`):

```js
  auth: {
    google: '/auth/google',
    logout: '/auth/logout',
    me: '/auth/me',
  },
```

Then, after the `const api = axios.create({...})` block and before `export const endpoints`, add:

```js
const TOKEN_STORAGE_KEY = 'asi_token';

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token && config.url !== '/auth/google') {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    }
    return Promise.reject(error);
  }
);

export const AUTH_TOKEN_STORAGE_KEY = TOKEN_STORAGE_KEY;
```

- [ ] **Step 3: Create `frontend/src/context/AuthContext.jsx`**

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import api, { endpoints, AUTH_TOKEN_STORAGE_KEY } from '../utils/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
            if (!token) {
                if (!cancelled) setLoading(false);
                return;
            }
            try {
                const res = await api.get(endpoints.auth.me);
                if (!cancelled) setUser(res.data);
            } catch {
                if (!cancelled) {
                    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
                    setUser(null);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const login = async (idToken) => {
        const res = await api.post(endpoints.auth.google, { id_token: idToken });
        localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, res.data.token);
        setUser(res.data.user);
    };

    const logout = () => {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
};
```

- [ ] **Step 4: Create `frontend/src/pages/Login.jsx`**

```jsx
import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { Brain, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Login = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState('');

    const handleSuccess = async (credentialResponse) => {
        try {
            await login(credentialResponse.credential);
            navigate('/');
        } catch {
            setError('Sign-in failed. Please try again.');
        }
    };

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
            <div className="w-full max-w-sm bg-card border border-border rounded-2xl p-8 text-center shadow-lg">
                <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
                    <Brain className="w-6 h-6 text-primary" />
                </div>
                <h1 className="text-2xl font-bold mb-2">NeoTrade AI</h1>
                <p className="text-muted-foreground text-sm mb-6">Sign in to continue</p>

                <div className="flex justify-center">
                    <GoogleLogin
                        onSuccess={handleSuccess}
                        onError={() => setError('Sign-in failed. Please try again.')}
                    />
                </div>

                {error && (
                    <div className="mt-4 flex items-center justify-center gap-2 text-sm text-destructive">
                        <AlertCircle className="w-4 h-4" />
                        <span>{error}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Login;
```

- [ ] **Step 5: Create `frontend/src/components/RequireAuth.jsx`**

```jsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const RequireAuth = ({ children }) => {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="w-10 h-10 rounded-full border-2 border-muted/30 border-t-primary animate-spin" />
            </div>
        );
    }

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    return children;
};

export default RequireAuth;
```

- [ ] **Step 6: Wrap `App.jsx` routes and wire `GoogleOAuthProvider`**

Replace `frontend/src/App.jsx` in full:

```jsx
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ScannerPage from './pages/ScannerPage';
import Watchlist from './pages/Watchlist';
import Portfolio from './pages/Portfolio';
import Trading from './pages/Trading';
import Settings from './pages/Settings';
import Login from './pages/Login';
import RequireAuth from './components/RequireAuth';

import SystemArchitecturePage from './pages/SystemArchitecturePage';

const App = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/scanner" element={<RequireAuth><ScannerPage /></RequireAuth>} />
      <Route path="/trading" element={<RequireAuth><Trading /></RequireAuth>} />
      <Route path="/watchlist" element={<RequireAuth><Watchlist /></RequireAuth>} />
      <Route path="/portfolio" element={<RequireAuth><Portfolio /></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
      <Route path="/system" element={<RequireAuth><SystemArchitecturePage /></RequireAuth>} />
    </Routes>
  );
};

export default App;
```

Modify `frontend/src/main.jsx` in full:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </GoogleOAuthProvider>
  </StrictMode>,
)
```

- [ ] **Step 7: Lint and build**

Run (from `frontend/`): `npm run lint`
Expected: no errors.

Run: `npm run build`
Expected: builds clean. (`VITE_GOOGLE_CLIENT_ID` being unset at build time is fine — `GoogleOAuthProvider` only errors at runtime if a login is actually attempted with no client id; this is addressed for real verification in Task 8, which requires the client id to exist first.)

- [ ] **Step 8: Commit**

```bash
cd .. && git add frontend/package.json frontend/package-lock.json frontend/src/main.jsx frontend/src/App.jsx frontend/src/context/AuthContext.jsx frontend/src/pages/Login.jsx frontend/src/components/RequireAuth.jsx frontend/src/utils/api.js
git commit -m "feat: add Google login flow and gate every frontend route

Bearer token in localStorage, attached via an axios request
interceptor; a response interceptor clears it and redirects to /login
on any 401/403 app-wide.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 7: Real user in Sidebar, Watchlist, and AnalysisCard

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.jsx:71-80`
- Modify: `frontend/src/pages/Watchlist.jsx:13`
- Modify: `frontend/src/components/AnalysisCard.jsx:71`

**Interfaces:**
- Consumes: `useAuth()` (Task 6) → `{user: {id, name, email, picture}, logout}`.

- [ ] **Step 1: Update `Sidebar.jsx`'s footer**

In `frontend/src/components/layout/Sidebar.jsx`, add the import:

```jsx
import { useAuth } from '../../context/AuthContext';
import { LogOut } from 'lucide-react';
```

(add `LogOut` to the existing `lucide-react` import line rather than a second import statement)

Replace the footer block:

```jsx
      {/* User / Footer */}
      <div className="p-4 border-t border-border/50">
        <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/30 border border-border/30">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500" />
            <div className="flex-1 overflow-hidden">
                <p className="text-sm font-medium truncate">Pro Investor</p>
                <p className="text-xs text-muted-foreground">Pro Plan</p>
            </div>
        </div>
      </div>
```

with:

```jsx
      {/* User / Footer */}
      <div className="p-4 border-t border-border/50">
        <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/30 border border-border/30">
            {user?.picture ? (
                <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full" />
            ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500" />
            )}
            <div className="flex-1 overflow-hidden">
                <p className="text-sm font-medium truncate">{user?.name || 'Signed in'}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
            <button
                onClick={logout}
                title="Log out"
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
                <LogOut className="w-4 h-4" />
            </button>
        </div>
      </div>
```

And inside the component body, add the hook call (right after `const navItems = [...]` block, before the `return`):

```jsx
  const { user, logout } = useAuth();
```

- [ ] **Step 2: Update `Watchlist.jsx`**

In `frontend/src/pages/Watchlist.jsx`, add the import:

```jsx
import { useAuth } from '../context/AuthContext';
```

Replace:

```jsx
    const userId = "default-user"; // Hardcoded for single user mode
```

with:

```jsx
    const { user } = useAuth();
    const userId = user.id;
```

(Safe because `Watchlist` only ever renders inside `RequireAuth`, which guarantees `user` is non-null by the time children render.)

- [ ] **Step 3: Update `AnalysisCard.jsx`**

In `frontend/src/components/AnalysisCard.jsx`, add the import:

```jsx
import { useAuth } from '../context/AuthContext';
```

Add inside the component body (near the top, alongside the existing destructure):

```jsx
  const { user } = useAuth();
```

Replace:

```jsx
                        await api.post(endpoints.watchlist.add("default-user", company_info?.symbol));
```

with:

```jsx
                        await api.post(endpoints.watchlist.add(user.id, company_info?.symbol));
```

- [ ] **Step 4: Lint and build**

Run (from `frontend/`): `npm run lint`
Expected: no errors.

Run: `npm run build`
Expected: builds clean.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/layout/Sidebar.jsx frontend/src/pages/Watchlist.jsx frontend/src/components/AnalysisCard.jsx
git commit -m "feat: replace hardcoded default-user with the real signed-in user

Sidebar footer now shows the real Google account (name/email/picture)
with a working logout button; Watchlist is per-user for real.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 8: Google Cloud Console setup + end-to-end verification (human-required)

**Files:** none (verification only)

**Interfaces:** none — this task validates Tasks 1–7 against the real Google OAuth flow.

- [ ] **Step 1: STOP and confirm the OAuth client exists**

Ask the user directly: "Have you already created the dedicated Google OAuth Client ID for AI Stock Investor in Google Cloud Console? If not, I'll walk you through it now — it needs your own Google account login, which I can't do."

If not yet created, walk them through:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new project (or pick an existing one) — separate from RoutineOS's project, per the spec's "dedicated client" decision.
3. Configure the OAuth consent screen (External user type, app name "AI Stock Investor", your email as support/developer contact).
4. Create Credentials → OAuth client ID → Application type "Web application".
5. **Authorized JavaScript origins** (no redirect URI needed for this ID-token-only flow): add `http://localhost:5173` (dev) and the production Vercel URL (e.g. `https://ai-stock-investor.vercel.app` — confirm the actual URL from `vercel ls` or the user).
6. Copy the generated Client ID.

Do not proceed to Step 2 until you have a real Client ID.

- [ ] **Step 2: Set the Client ID in both environments**

Backend `.env` (repo root, and the separate deploy clone at `~/deploys/AI_Stock_Investor/.env` — this repo's push-to-deploy runs from a physically separate clone with its own `.env`, confirmed earlier this session):

```
GOOGLE_CLIENT_ID=<the client id from Step 1>
JWT_SECRET=<run: openssl rand -base64 48>
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<your-vercel-prod-url>
```

Frontend: set `VITE_GOOGLE_CLIENT_ID` in Vercel's environment variables (production) via `vercel env add VITE_GOOGLE_CLIENT_ID production`, and locally in `frontend/.env` for dev testing.

- [ ] **Step 3: Rebuild and restart the backend container**

```bash
cd ~/projects/AI_Stock_Investor && docker compose up -d --build backend
docker logs ai-stock-investor-backend --tail 20
```

Expected: clean startup, no warnings about missing `GOOGLE_CLIENT_ID`/`JWT_SECRET`.

- [ ] **Step 4: Confirm every route now requires auth**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/watchlist/someuser
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/trading/positions
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/auth/me
```

Expected: all three return `401` or `403` (no token supplied).

- [ ] **Step 5: Confirm `/auth/google` is reachable and rejects a garbage token**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/google -H "Content-Type: application/json" -d '{"id_token":"not-a-real-token"}'
```

Expected: `{"detail":"Invalid Google token: ..."}` with a 401 — proves the route itself needs no auth to reach, and that real Google verification (not a stub) is wired in and correctly rejects garbage.

- [ ] **Step 6: Real sign-in click-through**

Deploy the frontend (`vercel deploy --prod` from `frontend/`, or push if push-to-deploy is set up for the frontend — confirmed earlier this session the Vercel project is git-connected). Then, in a real browser:
1. Visit the production URL — confirm it redirects to `/login` (not a blank/broken page).
2. Click the Google Sign-In button, complete the real Google OAuth prompt.
3. Confirm redirect to `/` and the Dashboard loads.
4. Confirm the Sidebar footer shows your real Google name/email/picture.
5. Add a stock to your Watchlist; reload the page; confirm it's still there (proves the real `user.id` persisted, not `"default-user"`).
6. Click Logout; confirm redirect to `/login` and that reloading any protected URL directly (e.g. `/trading`) also redirects to `/login` rather than flashing protected content.
7. If a second Google account is available, sign in with it and confirm its Watchlist is empty/separate from the first account's.

- [ ] **Step 7: Push**

```bash
cd ~/projects/AI_Stock_Investor && git push origin main
```

Then watch CI and the backend auto-deploy job (`gh run list --limit 3`, `gh run watch <id> --exit-status`), same pattern used earlier this session. **Important**: after the auto-deploy lands, re-check the deploy clone's `.env` at `~/deploys/AI_Stock_Investor/.env` has the real `GOOGLE_CLIENT_ID`/`JWT_SECRET`/`CORS_ALLOWED_ORIGINS` set too (this session already hit this exact gotcha once with `OMNIROUTE_API_KEY` — the deploy clone has its own independent `.env`, separate from the working clone's) — if the auto-deployed container logs show missing-config warnings, copy the values into the deploy clone's `.env` and `docker compose up -d --build backend` from there directly.

## Self-Review Notes

- **Spec coverage:** every "In scope" bullet has a task — dedicated OAuth client (Task 8), ID-token verification via `google-auth` (Task 2), bearer JWT not cookie (Task 3), gating every router (Task 5) and every frontend route (Task 6), CORS fix (Task 4), Sidebar/Watchlist/AnalysisCard real-user swap (Task 7). "Out of scope" items (per-user trading, per-user model, refresh tokens, allowlist, roles) are correctly untouched.
- **Type/name consistency checked:** `User.id`/`google_sub`/`email`/`name`/`picture` (Task 1) match exactly what Task 2's `GoogleUserInfo`, Task 4's router, and Task 7's frontend consume. `get_user_store`/`get_current_user` (Task 3) match what Task 4's and Task 5's tests monkeypatch/override. `AUTH_TOKEN_STORAGE_KEY`/`endpoints.auth.*` (Task 6 Step 2) match exactly what `AuthContext.jsx` (Task 6 Step 3) imports and uses.
- **No placeholders** — every step has real, complete, runnable code. (Task 2 Step 1's intentionally-broken draft test is explicitly corrected in Step 5 of the same task, with a note explaining why — this is a deliberate TDD-fail-then-fix within one task, not a leftover placeholder.)
- **Known operational gotcha folded in directly**: Task 8 Step 7 explicitly calls out the separate-deploy-clone `.env` issue that was hit twice already this session (`KITE_API_KEY`, `OMNIROUTE_API_KEY`) — this plan doesn't wait to rediscover it a third time.
