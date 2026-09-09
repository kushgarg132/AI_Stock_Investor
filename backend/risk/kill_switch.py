"""Daily loss kill-switch: the persisted half. `should_trip` is the pure
decision (equity <= -limit); this store is what makes the decision stick --
once tripped for a user's trading day, it never re-arms on its own, even
across a stopped-and-restarted run. Collection `kill_switch_trips`, one
document per (user_id, IST calendar date).
"""

from datetime import date, datetime, timezone
from typing import Optional


def should_trip(equity: float, daily_loss_limit: float) -> bool:
    """`equity` is realized + unrealized P&L (Portfolio.equity's meaning),
    so a loss is negative. Trips at or past the configured limit."""
    return equity <= -abs(daily_loss_limit)


class KillSwitchStore:
    def __init__(self, db) -> None:
        self._db = db

    @property
    def collection(self):
        return self._db["kill_switch_trips"]

    @staticmethod
    def _doc_id(user_id: str, trading_day: date) -> str:
        return f"{user_id}:{trading_day.isoformat()}"

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("user_id")

    async def is_tripped(self, user_id: str, trading_day: date) -> Optional[dict]:
        return await self.collection.find_one({"_id": self._doc_id(user_id, trading_day)})

    async def trip(self, user_id: str, trading_day: date, reason: str, equity: float) -> None:
        """Idempotent within a day: `$setOnInsert` means a second call the
        same day (e.g. a restarted run re-detecting the same breach) cannot
        move when the trip is considered to have started or overwrite its
        original reason -- that would be a silent re-arm."""
        await self.collection.update_one(
            {"_id": self._doc_id(user_id, trading_day)},
            {"$setOnInsert": {
                "user_id": user_id,
                "trading_day": trading_day.isoformat(),
                "reason": reason,
                "equity": equity,
                "tripped_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
