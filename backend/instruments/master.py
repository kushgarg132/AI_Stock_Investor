import logging
import re
from typing import Optional

from backend.instruments.models import Instrument

logger = logging.getLogger(__name__)


def _to_instrument(doc: dict) -> Instrument:
    doc = dict(doc)
    doc.pop("_id", None)
    return Instrument(**doc)


class InstrumentMaster:
    """Mongo-backed instrument master. Collection `instruments`, indexed on
    (exchange, tradingsymbol) unique and instrument_token unique."""

    def __init__(self, db):
        self.collection = db["instruments"]

    async def ensure_indexes(self):
        await self.collection.create_index([("exchange", 1), ("tradingsymbol", 1)], unique=True)
        await self.collection.create_index("instrument_token", unique=True)

    async def upsert_many(self, instruments: list[Instrument]) -> int:
        """Upserts by (exchange, tradingsymbol). Returns the count of documents
        actually inserted or changed (re-running with identical data is a no-op)."""
        count = 0
        for instrument in instruments:
            result = await self.collection.update_one(
                {"exchange": instrument.exchange, "tradingsymbol": instrument.tradingsymbol},
                {"$set": instrument.model_dump()},
                upsert=True,
            )
            if result.upserted_id is not None or result.modified_count:
                count += 1
        return count

    async def get(self, exchange: str, tradingsymbol: str) -> Optional[Instrument]:
        doc = await self.collection.find_one(
            {"exchange": exchange, "tradingsymbol": tradingsymbol.upper()}
        )
        return _to_instrument(doc) if doc else None

    async def get_by_token(self, token: int) -> Optional[Instrument]:
        doc = await self.collection.find_one({"instrument_token": token})
        return _to_instrument(doc) if doc else None

    async def search(self, query: str, limit: int = 10) -> list[Instrument]:
        """Case-insensitive substring match against tradingsymbol/name. Exact
        tradingsymbol match (case-insensitive) is ranked first."""
        pattern = {"$regex": re.escape(query), "$options": "i"}
        cursor = self.collection.find(
            {"$or": [{"tradingsymbol": pattern}, {"name": pattern}]}
        ).limit(max(limit * 3, limit))
        docs = await cursor.to_list(length=None)
        instruments = [_to_instrument(doc) for doc in docs]

        query_upper = query.upper()
        instruments.sort(key=lambda inst: inst.tradingsymbol.upper() != query_upper)
        return instruments[:limit]
