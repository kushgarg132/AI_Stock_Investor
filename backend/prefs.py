"""Per-user trading preferences (collection `user_prefs`).

What the scheduler scans, and the account size and exposure cap it sizes
against, are the user's own settings -- the engine used to take them from
whatever the /trading/start request happened to send, which leaves a
scheduled scan with nothing to go on.
"""

from datetime import datetime, timezone
from typing import Optional

from backend.components.quant.indian_stocks import ALL_SCAN_STOCKS

DEFAULTS = {
    "universe": list(ALL_SCAN_STOCKS),
    "account_size": 1_000_000.0,
    "max_exposure": 1_000_000.0,
    "scan_enabled": True,
    "omniroute_model": None,
}

EDITABLE = tuple(DEFAULTS)


class PrefsStore:
    def __init__(self, db) -> None:
        self.collection = db["user_prefs"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("user_id", unique=True)

    async def get(self, user_id: str) -> dict:
        doc = await self.collection.find_one({"user_id": user_id}) or {}
        return {**DEFAULTS, "user_id": user_id, **{k: doc[k] for k in EDITABLE if k in doc}}

    async def update(self, user_id: str, patch: dict) -> dict:
        changes = {k: v for k, v in patch.items() if k in EDITABLE and v is not None}
        if changes:
            changes["updated_at"] = datetime.now(timezone.utc)
            await self.collection.update_one(
                {"user_id": user_id}, {"$set": changes}, upsert=True
            )
        return await self.get(user_id)

    async def scan_enabled_users(self) -> list[dict]:
        """Users the scheduled scan should run for. A user who has never
        opened settings has no document at all, so absence means enabled --
        matching DEFAULTS rather than silently excluding them."""
        cursor = self.collection.find({"scan_enabled": False})
        opted_out = {doc["user_id"] for doc in await cursor.to_list(length=None)}

        users = await self.collection.database["users"].find({}).to_list(length=None)
        return [await self.get(u["id"]) for u in users if u["id"] not in opted_out]
