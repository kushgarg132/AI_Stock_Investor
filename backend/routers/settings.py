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
