"""Deployment-wide settings that used to be rewritten into .env at runtime
(collection `app_settings`, one document).

Writing .env from a request mutated shared process state, did not survive more
than one worker, and was reachable by anyone signed in. These settings are
genuinely deployment-wide rather than per-user, so they stay shared -- but
they live in the database and only an admin may change them.
"""

from datetime import datetime, timezone
from typing import Optional

_DOC_ID = "singleton"

# get_llm() is synchronous and runs per request, so it cannot await Mongo.
# The stored value is mirrored here: loaded once at startup, refreshed on
# write. Falls back to the configured default when nothing is stored.
_cached_llm_model: Optional[str] = None


def current_llm_model() -> str:
    from backend.configs.settings import settings

    return _cached_llm_model or settings.OMNIROUTE_MODEL


class AppSettingsStore:
    def __init__(self, db) -> None:
        self._db = db

    @property
    def collection(self):
        return self._db["app_settings"]

    async def get_llm_model(self) -> Optional[str]:
        doc = await self.collection.find_one({"_id": _DOC_ID})
        return (doc or {}).get("llm_model")

    async def set_llm_model(self, model: str) -> None:
        global _cached_llm_model
        await self.collection.update_one(
            {"_id": _DOC_ID},
            {"$set": {"llm_model": model, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        _cached_llm_model = model

    async def load_into_cache(self) -> None:
        global _cached_llm_model
        _cached_llm_model = await self.get_llm_model()
