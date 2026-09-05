# OmniRoute-only LLM + Model Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Gemini-API-key-management UI from Settings, rename the misleading `GEMINI_API_KEY(S)` config to `OMNIROUTE_API_KEY(S)`, and add a searchable OmniRoute model picker so the user can change which model the app uses without editing `.env`.

**Architecture:** `backend/llm.py` already builds every LLM client as `ChatOpenAI` pointed at OmniRoute (`settings.OMNIROUTE_BASE_URL`/`settings.OMNIROUTE_MODEL`) — only naming and the settings HTTP surface need to change. Replace `backend/routers/settings.py`'s `/settings/gemini-keys` GET/POST pair with three new routes (`GET /settings/omniroute-models` proxying OmniRoute's own `/v1/models`, `GET`/`POST /settings/omniroute-model` to read/persist the selection), then swap `Settings.jsx`'s key-input card for a searchable model combobox.

**Tech Stack:** FastAPI, pydantic-settings, `httpx` (already a dependency), React 19, axios.

**Spec:** `docs/superpowers/specs/2026-09-05-omniroute-only-model-picker-design.md`

## Global Constraints

- No new dependencies — `httpx` is already in `backend/requirements.txt`.
- No `docker-compose.yml`/network change — `ai-stock-investor-backend` is already on `routineos_default` and can already reach `http://omniroute:20128/v1` (confirmed working this session).
- No capability filtering on the model list — nothing in this app calls `.bind_tools(...)` today, so any of the 648 models works with plain completion.
- Delete `/settings/gemini-keys` outright — no deprecated alias, nothing external depends on this app's own internal settings API.
- The OmniRoute gateway key (`OMNIROUTE_API_KEY`) is never read or returned by any route after this change — it's a pure ops secret edited directly in `.env` on the VM.

---

### Task 1: Rename `GEMINI_API_KEY(S)` → `OMNIROUTE_API_KEY(S)` in settings and `llm.py`

**Files:**
- Modify: `backend/configs/settings.py:19-21,36-45`
- Modify: `backend/llm.py:70-74,119-123`
- Modify: `.env` (root, gitignored — one line renamed, not committed)
- Test: `backend/tests/test_settings.py` (new)

**Interfaces:**
- Produces: `Settings.OMNIROUTE_API_KEY: Optional[str]`, `Settings.OMNIROUTE_API_KEYS: List[str]` (replaces `GEMINI_API_KEY`/`GEMINI_API_KEYS` everywhere). `LLMService.keys` now sourced from `settings.OMNIROUTE_API_KEYS`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_settings.py`:

```python
from backend.configs.settings import Settings


def test_single_omniroute_api_key_splits_on_comma():
    s = Settings(OMNIROUTE_API_KEY="key-a,key-b")
    assert s.OMNIROUTE_API_KEYS == ["key-a", "key-b"]


def test_explicit_omniroute_api_keys_list_takes_precedence():
    s = Settings(OMNIROUTE_API_KEY="ignored", OMNIROUTE_API_KEYS=["real-key"])
    assert s.OMNIROUTE_API_KEYS == ["real-key"]


def test_no_keys_configured_returns_empty_list():
    s = Settings(OMNIROUTE_API_KEY=None, OMNIROUTE_API_KEYS=[])
    assert s.OMNIROUTE_API_KEYS == []
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python3 -m pytest tests/test_settings.py -v`
Expected: FAIL — `Settings` has no field `OMNIROUTE_API_KEY` (still named `GEMINI_API_KEY`), pydantic will either reject the unknown kwarg or the assertions will fail depending on `extra` config; either way it must not pass yet.

- [ ] **Step 3: Rename the fields in `settings.py`**

In `backend/configs/settings.py`, replace:

```python
    # API Keys (Set these in your .env file)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_API_KEYS: List[str] = []
    
    # OmniRoute (self-hosted OpenAI-compatible gateway) -- GEMINI_API_KEY(S) above
    # holds the OmniRoute gateway key, not a real Google key, when this is used.
    OMNIROUTE_BASE_URL: str = "http://omniroute:20128/v1"
    OMNIROUTE_MODEL: str = "antigravity/gemini-2.5-flash"
```

with:

```python
    # OmniRoute (self-hosted OpenAI-compatible gateway) -- the only LLM
    # provider this app uses. OMNIROUTE_API_KEY(S) holds the gateway key
    # issued from the OmniRoute dashboard's Endpoints page, not a Google key.
    OMNIROUTE_API_KEY: Optional[str] = None
    OMNIROUTE_API_KEYS: List[str] = []
    OMNIROUTE_BASE_URL: str = "http://omniroute:20128/v1"
    OMNIROUTE_MODEL: str = "antigravity/gemini-2.5-flash"
```

And replace the validator:

```python
    @field_validator("GEMINI_API_KEYS", mode="before")
    @classmethod
    def assemble_gemini_keys(cls, v: Optional[List[str]], info: ValidationInfo) -> List[str]:
        if isinstance(v, list) and v:
            return v
        # Fallback to splitting the single key if it contains commas, or just using it
        values = info.data.get("GEMINI_API_KEY")
        if values:
            return [k.strip() for k in values.split(",") if k.strip()]
        return []
```

with:

```python
    @field_validator("OMNIROUTE_API_KEYS", mode="before")
    @classmethod
    def assemble_omniroute_keys(cls, v: Optional[List[str]], info: ValidationInfo) -> List[str]:
        if isinstance(v, list) and v:
            return v
        # Fallback to splitting the single key if it contains commas, or just using it
        values = info.data.get("OMNIROUTE_API_KEY")
        if values:
            return [k.strip() for k in values.split(",") if k.strip()]
        return []
```

- [ ] **Step 4: Rename the two `llm.py` call sites**

In `backend/llm.py`, `LLMService.__init__` (lines 70-74):

```python
    def __init__(self):
        # We prefer using LangChain for agents, but this client is for direct single usage if needed
        self.keys = settings.GEMINI_API_KEYS
        if not self.keys:
            logger.warning("GEMINI_API_KEY(S) not set. LLM features will be disabled.")
```

becomes:

```python
    def __init__(self):
        # We prefer using LangChain for agents, but this client is for direct single usage if needed
        self.keys = settings.OMNIROUTE_API_KEYS
        if not self.keys:
            logger.warning("OMNIROUTE_API_KEY(S) not set. LLM features will be disabled.")
```

And `reload_keys` (lines 119-123):

```python
    def reload_keys(self):
        """Reloads keys from global settings"""
        from backend.configs.settings import settings
        self.keys = settings.GEMINI_API_KEYS
        logger.info(f"LLMService keys reloaded. Count: {len(self.keys)}")
```

becomes:

```python
    def reload_keys(self):
        """Reloads keys from global settings"""
        from backend.configs.settings import settings
        self.keys = settings.OMNIROUTE_API_KEYS
        logger.info(f"LLMService keys reloaded. Count: {len(self.keys)}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_settings.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full backend suite to confirm no regressions**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (all tests — no call site outside `settings.py`/`llm.py`/the settings router references `GEMINI_API_KEY` by name, confirmed during research)

- [ ] **Step 7: Rename the live `.env` line (not a git-tracked change — `.env` is gitignored)**

Run from the repo root (`~/projects/AI_Stock_Investor`):

```bash
sed -i 's/^GEMINI_API_KEY=/OMNIROUTE_API_KEY=/' .env
grep -c '^OMNIROUTE_API_KEY=' .env   # expect: 1
grep -c '^GEMINI_API_KEY=' .env     # expect: 0
```

This preserves the existing real, working gateway key value under the new name — no new key needs to be generated.

- [ ] **Step 8: Commit**

```bash
git add backend/configs/settings.py backend/llm.py backend/tests/test_settings.py
git commit -m "refactor: rename GEMINI_API_KEY(S) to OMNIROUTE_API_KEY(S)

The app has been routing every LLM call through the OmniRoute gateway
for a while (llm.py builds ChatOpenAI against OMNIROUTE_BASE_URL) -- the
Gemini naming was legacy and actively misleading now that the Settings
UI is dropping all Gemini framing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 2: Replace `/settings/gemini-keys` with the OmniRoute model routes

**Files:**
- Modify: `backend/routers/settings.py` (full rewrite)
- Test: `backend/tests/test_settings_router.py` (new)

**Interfaces:**
- Consumes: `settings.OMNIROUTE_BASE_URL`, `settings.OMNIROUTE_MODEL` (from Task 1).
- Produces: `GET /settings/omniroute-models` → `[{"id": str}, ...]`. `GET /settings/omniroute-model` → `{"model": str}`. `POST /settings/omniroute-model` (body `{"model": str}`) → `{"message": str}` (200) or 400 (empty model) or 500 (write failure). Module-level `ENV_PATH: Path` constant (monkeypatchable by tests).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_settings_router.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_settings_router.py -v`
Expected: FAIL — none of these routes exist yet (still `/settings/gemini-keys`).

- [ ] **Step 3: Rewrite `backend/routers/settings.py`**

Replace the entire file contents with:

```python
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.configs.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ENV_PATH = Path(".env")


@router.get("/settings/omniroute-models")
async def list_omniroute_models():
    """Proxies OmniRoute's OpenAI-compatible GET /models so the frontend can
    offer a searchable picker instead of a hardcoded model string. Returns
    only `id` per entry -- the picker doesn't need context_length/capabilities."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.OMNIROUTE_BASE_URL}/models")
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch OmniRoute model list: {e}")
        raise HTTPException(status_code=502, detail="Could not reach OmniRoute gateway")

    data = resp.json().get("data", [])
    return [{"id": m["id"]} for m in data]


@router.get("/settings/omniroute-model")
async def get_omniroute_model():
    return {"model": settings.OMNIROUTE_MODEL}


class ModelUpdate(BaseModel):
    model: str


@router.post("/settings/omniroute-model")
async def set_omniroute_model(update: ModelUpdate):
    """Persists the selected model to .env and updates the running process's
    settings in-memory so llm.py's get_llm() picks it up on the very next
    call -- no restart needed."""
    new_model = update.model.strip()
    if not new_model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    try:
        content = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []

        model_found = False
        new_content = []
        for line in content:
            if line.startswith("OMNIROUTE_MODEL="):
                new_content.append(f"OMNIROUTE_MODEL={new_model}")
                model_found = True
            else:
                new_content.append(line)

        if not model_found:
            new_content.append(f"OMNIROUTE_MODEL={new_model}")

        ENV_PATH.write_text("\n".join(new_content) + "\n")

        settings.OMNIROUTE_MODEL = new_model
        logger.info(f"OmniRoute model updated to {new_model!r} via Settings API.")
        return {"message": "Model updated successfully"}

    except OSError as e:
        logger.error(f"Failed to update .env file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save model selection")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_settings_router.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (no other test references `/settings/gemini-keys` or `GeminiKeyUpdate`)

- [ ] **Step 6: Commit**

```bash
git add backend/routers/settings.py backend/tests/test_settings_router.py
git commit -m "feat: replace /settings/gemini-keys with OmniRoute model routes

GET /settings/omniroute-models proxies OmniRoute's own /v1/models (648
models today). GET/POST /settings/omniroute-model reads/persists the
selected model to .env, same file-rewrite pattern the old route used.
The gateway key itself is no longer readable or writable via any route
-- it's a pure ops secret now, edited directly in .env.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 3: Replace Settings.jsx's Gemini key card with a searchable model picker

**Files:**
- Modify: `frontend/src/utils/api.js`
- Modify: `frontend/src/pages/Settings.jsx` (full rewrite)

**Interfaces:**
- Consumes: `GET /settings/omniroute-models` → `[{id}]`, `GET`/`POST /settings/omniroute-model` (from Task 2).
- Produces: `endpoints.settings.omnirouteModels`, `endpoints.settings.omnirouteModel` in `api.js`.

- [ ] **Step 1: Add the settings endpoints to `api.js`**

In `frontend/src/utils/api.js`, add a `settings` key to the `endpoints` object (alongside the existing `trading` key):

```js
  settings: {
    omnirouteModels: '/settings/omniroute-models',
    omnirouteModel: '/settings/omniroute-model',
  },
```

- [ ] **Step 2: Rewrite `frontend/src/pages/Settings.jsx`**

Replace the entire file contents with:

```jsx
import React, { useState, useEffect, useMemo } from 'react';
import Layout from '../components/Layout';
import { UserCog, Cpu, Save, CheckCircle, AlertCircle, Search } from 'lucide-react';
import api, { endpoints } from '../utils/api';

const Settings = () => {
    const [models, setModels] = useState([]);
    const [currentModel, setCurrentModel] = useState('');
    const [query, setQuery] = useState('');
    const [selectedModel, setSelectedModel] = useState('');
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [status, setStatus] = useState({ loading: false, message: '', type: '' });
    const [loadError, setLoadError] = useState('');

    useEffect(() => {
        fetchModelData();
    }, []);

    const fetchModelData = async () => {
        try {
            const [modelsRes, currentRes] = await Promise.all([
                api.get(endpoints.settings.omnirouteModels),
                api.get(endpoints.settings.omnirouteModel),
            ]);
            setModels(modelsRes.data);
            setCurrentModel(currentRes.data.model);
            setSelectedModel(currentRes.data.model);
            setLoadError('');
        } catch {
            setLoadError('Could not load models from the OmniRoute gateway.');
        }
    };

    const filteredModels = useMemo(() => {
        if (!query.trim()) return models;
        const q = query.trim().toLowerCase();
        return models.filter((m) => m.id.toLowerCase().includes(q));
    }, [models, query]);

    const handleSave = async () => {
        if (!selectedModel.trim()) return;
        setStatus({ loading: true, message: '', type: '' });
        try {
            await api.post(endpoints.settings.omnirouteModel, { model: selectedModel });
            setStatus({ loading: false, message: 'Model saved successfully!', type: 'success' });
            setCurrentModel(selectedModel);
        } catch {
            setStatus({ loading: false, message: 'Failed to save model', type: 'error' });
        }
    };

    return (
        <Layout>
            <div className="p-8 max-w-4xl mx-auto">
                <div className="flex items-center space-x-4 mb-8">
                    <div className="p-3 bg-primary/10 rounded-xl">
                        <UserCog className="w-8 h-8 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold">Settings</h1>
                        <p className="text-muted-foreground">Manage your application preferences</p>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="bg-card border border-border/50 rounded-2xl p-6 shadow-sm backdrop-blur-sm">
                        <div className="flex items-center space-x-3 mb-6">
                            <Cpu className="w-5 h-5 text-indigo-500" />
                            <h2 className="text-xl font-semibold">OmniRoute Model</h2>
                        </div>

                        {loadError ? (
                            <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-3 text-destructive">
                                <AlertCircle className="w-5 h-5" />
                                <p className="text-sm">{loadError}</p>
                            </div>
                        ) : (
                            <>
                                {currentModel && (
                                    <div className="mb-6 p-4 bg-muted/50 rounded-lg border border-border/50">
                                        <p className="text-sm text-muted-foreground mb-1">Current Model:</p>
                                        <code className="text-sm font-mono text-primary">{currentModel}</code>
                                    </div>
                                )}

                                <div className="relative">
                                    <label className="block text-sm font-medium mb-2 pl-1">Select Model</label>
                                    <div className="relative">
                                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <input
                                            type="text"
                                            value={dropdownOpen ? query : selectedModel}
                                            onFocus={() => { setDropdownOpen(true); setQuery(''); }}
                                            onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
                                            onChange={(e) => setQuery(e.target.value)}
                                            placeholder="Search models (e.g. claude, gemini)..."
                                            className="w-full bg-background border border-border rounded-xl pl-11 pr-4 py-3 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                        />
                                    </div>
                                    {dropdownOpen && (
                                        <div className="absolute z-10 mt-1 w-full max-h-64 overflow-y-auto rounded-xl border border-border bg-popover shadow-xl custom-scrollbar">
                                            {filteredModels.length === 0 ? (
                                                <p className="px-4 py-3 text-sm text-muted-foreground">No matching models</p>
                                            ) : (
                                                filteredModels.slice(0, 100).map((m) => (
                                                    <button
                                                        key={m.id}
                                                        type="button"
                                                        onMouseDown={(e) => e.preventDefault()}
                                                        onClick={() => {
                                                            setSelectedModel(m.id);
                                                            setDropdownOpen(false);
                                                        }}
                                                        className="w-full text-left px-4 py-2.5 text-sm font-mono hover:bg-muted/50 transition-colors"
                                                    >
                                                        {m.id}
                                                    </button>
                                                ))
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className="flex items-center justify-between pt-6">
                                    {status.message && (
                                        <p className={`text-sm flex items-center ${status.type === 'success' ? 'text-green-500' : 'text-red-500'}`}>
                                            {status.type === 'success' ? (
                                                <CheckCircle className="w-4 h-4 mr-1.5" />
                                            ) : (
                                                <AlertCircle className="w-4 h-4 mr-1.5" />
                                            )}
                                            {status.message}
                                        </p>
                                    )}
                                    <button
                                        onClick={handleSave}
                                        disabled={status.loading || !selectedModel.trim() || selectedModel === currentModel}
                                        className={`ml-auto flex items-center space-x-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all shadow-lg shadow-primary/20 ${
                                            (status.loading || !selectedModel.trim() || selectedModel === currentModel) ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'
                                        }`}
                                    >
                                        <Save className="w-4 h-4" />
                                        <span>{status.loading ? 'Saving...' : 'Save Model'}</span>
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default Settings;
```

Note: `onMouseDown={(e) => e.preventDefault()}` on each dropdown option prevents the input's `onBlur` from closing the dropdown before the `onClick` fires (the 150ms `onBlur` delay is a fallback for keyboard/other blur paths, not the primary mouse-click guard).

- [ ] **Step 3: Lint and build**

Run (from `frontend/`): `npm run lint`
Expected: no errors (no `motion`/JSX-detection gaps here — this file uses no framer-motion).

Run: `npm run build`
Expected: builds clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/api.js frontend/src/pages/Settings.jsx
git commit -m "feat: replace Gemini API key UI with OmniRoute model picker

Settings no longer exposes any API-key input -- the OmniRoute gateway
key is a pure ops secret now. In its place, a searchable combobox
(client-side filtered, no debounce needed for ~650 models) lets the
user pick which OmniRoute model the app uses, persisted via the new
GET/POST /settings/omniroute-model routes.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011zb4k3CKGfoW3XXY4H1CqC"
```

---

### Task 4: End-to-end verification against the live stack

**Files:** none (verification only)

**Interfaces:** none (this task produces no new interfaces; it validates Tasks 1-3 against the real running backend container)

- [ ] **Step 1: Rebuild and redeploy the backend container**

```bash
cd ~/projects/AI_Stock_Investor && docker compose up -d --build backend
```

Wait for it to report `Started`, then confirm no startup errors:

```bash
docker logs ai-stock-investor-backend --tail 20
```

Expected: `Database connected.`, `Instrument master seeded: 0 upserted.` (idempotent re-seed), `Application startup complete.` — no `OMNIROUTE_API_KEY` warnings (the renamed `.env` line should already carry the real key from Task 1 Step 7).

- [ ] **Step 2: Curl the new routes directly**

```bash
curl -s http://localhost:8000/api/v1/settings/omniroute-models | head -c 300
echo
curl -s http://localhost:8000/api/v1/settings/omniroute-model
echo
curl -s -X POST http://localhost:8000/api/v1/settings/omniroute-model \
  -H "Content-Type: application/json" -d '{"model":"antigravity/gemini-2.5-flash"}'
echo
curl -s http://localhost:8000/api/v1/settings/omniroute-model
```

Expected: first call returns a JSON array starting with `[{"id":"...`; second/fourth calls return `{"model":"antigravity/gemini-2.5-flash"}` (or whatever's currently set); the POST returns `{"message":"Model updated successfully"}`.

- [ ] **Step 3: Confirm the old route is actually gone**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/settings/gemini-keys
```

Expected: `404`.

- [ ] **Step 4: Confirm `.env`'s `OMNIROUTE_MODEL=` line actually changed**

```bash
grep '^OMNIROUTE_MODEL=' ~/projects/AI_Stock_Investor/.env
```

Expected: matches whatever was POSTed in Step 2.

- [ ] **Step 5: Confirm a real LLM call still works end-to-end**

Trigger any existing endpoint that goes through `llm_service` (e.g. the analyze endpoint used earlier this session), and tail logs to confirm no `OMNIROUTE_API_KEY`-related errors:

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/analyze/RELIANCE.NS -o /dev/null -w "%{http_code}\n"
docker logs ai-stock-investor-backend --tail 15
```

Expected: `200`, and logs show normal `httpx2` requests to `http://omniroute:20128/v1/chat/completions` with `200 OK` responses (same pattern seen earlier this session before the rename).

- [ ] **Step 6: Push**

```bash
cd ~/projects/AI_Stock_Investor && git push origin main
```

Then watch CI and the backend auto-deploy job (`gh run list --limit 3`, `gh run watch <id> --exit-status`) to confirm they land clean, same as earlier this session.

## Self-Review Notes

- **Spec coverage:** Every "In scope" bullet from the spec has a task: rename (Task 1), route replacement (Task 2), frontend picker (Task 3), verification including the "old route deleted" check (Task 4). "Out of scope" items (capability filtering, `MultiKeyChain` changes, Google login) are correctly untouched.
- **Type/name consistency checked:** `ENV_PATH` (Task 2) matches what Task 2's tests monkeypatch; `endpoints.settings.omnirouteModels`/`omnirouteModel` (Task 3 Step 1) match exactly what Task 3 Step 2's `Settings.jsx` calls; `OMNIROUTE_API_KEY(S)` (Task 1) matches what Task 1's `llm.py` edits reference.
- **No placeholders** — every step has real, complete code, not descriptions of code.
