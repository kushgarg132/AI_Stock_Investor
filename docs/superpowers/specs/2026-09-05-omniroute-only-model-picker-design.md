# OmniRoute-only LLM + model picker

## Context

`backend/llm.py` already builds every LLM client as `ChatOpenAI` pointed at
`settings.OMNIROUTE_BASE_URL`/`settings.OMNIROUTE_MODEL` — this app has been
routing through the self-hosted OmniRoute gateway under the hood for a while.
What's left over is naming and UX debt: the settings/env vars and the
`/settings/gemini-keys` route + Settings.jsx UI still call the gateway key a
"Gemini API key" and let the user paste one in, even though the value is
actually an OmniRoute gateway key (issued from the OmniRoute dashboard, not
Google) and there's no way to pick which OmniRoute model gets used — it's
hardcoded to `antigravity/gemini-2.5-flash`.

The user asked to (1) remove the API-key-management UI from Settings
entirely, (2) always use OmniRoute (already true internally), and (3) add a
Settings dropdown to pick the OmniRoute model. This spec covers only that —
Google login is a separate, independent sub-project brainstormed separately.

## Scope

**In scope:**
- Rename `GEMINI_API_KEY`/`GEMINI_API_KEYS` → `OMNIROUTE_API_KEY`/
  `OMNIROUTE_API_KEYS` in `backend/configs/settings.py` and `.env` (the old
  name is actively misleading now that all Gemini framing is being removed
  from the UI; `.env` already holds a real, working key under the old name).
- Delete `backend/routers/settings.py`'s `/settings/gemini-keys` GET/POST
  pair outright (no deprecated alias — nothing external depends on this
  app's own internal settings API).
- Add `GET /settings/omniroute-models` (proxies OmniRoute's `/v1/models`,
  confirmed reachable at `http://omniroute:20128/v1/models` from the
  `ai-stock-investor-backend` container, 648 models today, `provider/model`
  id format).
- Add `GET /settings/omniroute-model` (current `OMNIROUTE_MODEL`) and
  `POST /settings/omniroute-model` (body `{model: str}`, persists to `.env`
  via the same file-rewrite pattern the old route used, mutates
  `settings.OMNIROUTE_MODEL` in-process — no restart needed since
  `get_llm()` reads `settings.OMNIROUTE_MODEL` fresh on every call).
- Replace Settings.jsx's "Gemini API Configuration" card with a "Model"
  card: fetch the model list once on mount, fetch current selection,
  client-side-filtered searchable combobox (648 items is cheap to filter
  in-browser, no debounced server round-trip needed), Save button.
- The gateway key itself becomes a pure ops secret — no route reads or
  writes it anymore; it's edited directly in `.env` on the VM if it ever
  needs to change.

**Out of scope (confirmed, not silently added):**
- Capability filtering (tool-calling-only models, etc.) — checked: nothing
  in this app actually calls `.bind_tools(...)` today (only defined on the
  `MultiKeyChain` wrapper class, never invoked by any agent), so plain
  completion works with any model in the list. Add filtering later only if
  the app starts using tool-calling.
- Any change to the multi-key fallback mechanism (`MultiKeyChain`) itself —
  untouched, still supports multiple `OMNIROUTE_API_KEYS` if ever needed.
- Google login (separate sub-project, separate spec).

## Backend design

`backend/configs/settings.py`:
- Rename the two fields and the `field_validator` that assembles the list
  from a comma-separated single value. Keep the same assembly logic (single
  `OMNIROUTE_API_KEY` env var splits into `OMNIROUTE_API_KEYS` if the list
  isn't explicitly set).

`backend/llm.py`:
- `LLMService.__init__` reads `settings.OMNIROUTE_API_KEYS` instead of
  `settings.GEMINI_API_KEYS`. `reload_keys()` same rename. No other logic
  changes — `get_llm()` already reads `settings.OMNIROUTE_MODEL` correctly.

`backend/routers/settings.py` (rewritten):
```python
@router.get("/omniroute-models")
async def list_omniroute_models():
    # httpx GET {settings.OMNIROUTE_BASE_URL}/models, return the `data` list
    # (id, owned_by at minimum -- frontend only needs `id` for the picker)

@router.get("/omniroute-model")
async def get_omniroute_model():
    return {"model": settings.OMNIROUTE_MODEL}

class ModelUpdate(BaseModel):
    model: str

@router.post("/omniroute-model")
async def set_omniroute_model(req: ModelUpdate):
    # same .env-rewrite pattern as the old POST /gemini-keys handler,
    # but for the OMNIROUTE_MODEL= line instead of GEMINI_API_KEY=
    settings.OMNIROUTE_MODEL = req.model
    return {"message": "Model updated"}
```

Error handling: if OmniRoute is unreachable, `list_omniroute_models` returns
a 502 with a clear detail message rather than crashing the whole Settings
page — the frontend shows an inline error and disables the picker, matching
this app's existing destructive-banner convention.

## Frontend design (`Settings.jsx`)

- On mount: `GET /settings/omniroute-models` (list) and
  `GET /settings/omniroute-model` (current selection), same pattern as
  today's `fetchKeyStatus`.
- Replace the key-input card with a searchable combobox: a text input
  filters the 648-item list client-side (plain substring match on `id`,
  case-insensitive — same filtering approach already used, mirrors the
  trading universe picker's UX without needing its debounce/server-search
  machinery since this list is small enough to hold in memory).
- Selecting an item + Save calls `POST /settings/omniroute-model`, then
  refetches current selection to confirm.
- Loading/error states follow the existing Settings.jsx pattern (inline
  status line, not a full banner, matching what's already there).

## Testing

- Backend: `backend/tests/test_settings_router.py` (new or extended) —
  mock the OmniRoute HTTP call for `list_omniroute_models` (don't hit the
  real network in unit tests), and a real round-trip test for
  get/post `omniroute-model` against a temp `.env` file.
- Manual verification against the live stack (same approach used earlier
  this session): rebuild the backend container, curl the three new routes
  directly, confirm `.env`'s `OMNIROUTE_MODEL=` line actually changes after
  a POST, confirm `npm run build`/`npm run lint` clean on the frontend.
