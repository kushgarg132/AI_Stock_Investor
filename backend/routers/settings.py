from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.configs.settings import settings
import os
from pathlib import Path
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class GeminiKeyUpdate(BaseModel):
    gemini_api_key: str

@router.get("/settings/gemini-keys")
async def get_gemini_key_status():
    """
    Returns the status of the Gemini API key.
    For security, we don't return the full key, just whether it's set and a masked version.
    """
    key = settings.GEMINI_API_KEY or (settings.GEMINI_API_KEYS[0] if settings.GEMINI_API_KEYS else None)
    
    if key:
        masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
        return {"is_set": True, "masked_key": masked_key}
    else:
        return {"is_set": False, "masked_key": None}

@router.post("/settings/gemini-keys")
async def update_gemini_key(key_update: GeminiKeyUpdate):
    """
    Updates the Gemini API key in the .env file and reloads the settings.
    """
    new_key = key_update.gemini_api_key.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    env_path = Path(".env")
    
    try:
        # Read existing .env content
        if env_path.exists():
            content = env_path.read_text().splitlines()
        else:
            content = []

        # Update or add the key
        key_found = False
        new_content = []
        for line in content:
            if line.startswith("GEMINI_API_KEY="):
                new_content.append(f"GEMINI_API_KEY={new_key}")
                key_found = True
            else:
                new_content.append(line)
        
        if not key_found:
            new_content.append(f"GEMINI_API_KEY={new_key}")

        # Write back to .env
        env_path.write_text("\n".join(new_content) + "\n")

        # Update in-memory settings
        os.environ["GEMINI_API_KEY"] = new_key
        settings.GEMINI_API_KEY = new_key
        # Update the list version as well if needed
        settings.GEMINI_API_KEYS = [new_key]

        # Reload LLM service keys
        from backend.llm import llm_service
        llm_service.reload_keys()

        logger.info("Gemini API key updated successfully via Settings API.")
        return {"message": "Gemini API key updated successfully"}

    except Exception as e:
        logger.error(f"Failed to update .env file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save API key")
