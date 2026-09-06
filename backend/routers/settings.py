import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependency import get_current_user
from backend.auth.models import User
from backend.configs.settings import settings
from backend.database import db
from backend.prefs import PrefsStore

router = APIRouter()
logger = logging.getLogger(__name__)

ENV_PATH = Path(".env")


def get_prefs_store() -> PrefsStore:
    return PrefsStore(db.db)


class PreferencesPatch(BaseModel):
    """Every field optional: the settings page saves one card at a time."""
    universe: Optional[list[str]] = None
    account_size: Optional[float] = None
    max_exposure: Optional[float] = None
    scan_enabled: Optional[bool] = None
    omniroute_model: Optional[str] = None


@router.get("/settings/preferences")
async def get_preferences(
    user: User = Depends(get_current_user),
    prefs: PrefsStore = Depends(get_prefs_store),
):
    return await prefs.get(user.id)


@router.put("/settings/preferences")
async def update_preferences(
    patch: PreferencesPatch,
    user: User = Depends(get_current_user),
    prefs: PrefsStore = Depends(get_prefs_store),
):
    return await prefs.update(user.id, patch.model_dump(exclude_none=True))


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


def _write_env_vars(updates: dict[str, str]) -> None:
    """Persists key=value pairs to .env, replacing existing lines for those
    keys or appending new ones. Callers are responsible for also updating
    the in-memory `settings` object so the running process picks up the
    change without a restart."""
    content = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)

    new_content = []
    for line in content:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in remaining:
            new_content.append(f"{key}={remaining.pop(key)}")
        else:
            new_content.append(line)

    for key, value in remaining.items():
        new_content.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_content) + "\n")


@router.post("/settings/omniroute-model")
async def set_omniroute_model(update: ModelUpdate):
    """Persists the selected model to .env and updates the running process's
    settings in-memory so llm.py's get_llm() picks it up on the very next
    call -- no restart needed."""
    new_model = update.model.strip()
    if not new_model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    try:
        _write_env_vars({"OMNIROUTE_MODEL": new_model})
        settings.OMNIROUTE_MODEL = new_model
        logger.info(f"OmniRoute model updated to {new_model!r} via Settings API.")
        return {"message": "Model updated successfully"}

    except OSError as e:
        logger.error(f"Failed to update .env file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save model selection")


class KiteCredentialsUpdate(BaseModel):
    api_key: str
    api_secret: str


@router.post("/settings/kite-credentials")
async def set_kite_credentials(update: KiteCredentialsUpdate, _user: User = Depends(get_current_user)):
    """Lets the operator paste their Zerodha Kite Connect app credentials in
    from the Settings page instead of SSHing in to edit .env by hand. Same
    per-deployment shape as the rest of this app (see backend/routers/broker.py's
    module docstring) -- one credential pair for the whole server, not
    per-user."""
    api_key = update.api_key.strip()
    api_secret = update.api_secret.strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Both API key and secret are required")

    try:
        _write_env_vars({"KITE_API_KEY": api_key, "KITE_API_SECRET": api_secret})
        settings.KITE_API_KEY = api_key
        settings.KITE_API_SECRET = api_secret
        logger.info("Kite API credentials updated via Settings API.")
        return {"message": "Credentials saved"}

    except OSError as e:
        logger.error(f"Failed to update .env file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save credentials")
