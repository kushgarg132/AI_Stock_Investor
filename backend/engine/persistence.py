"""Mongo-backed durability for the paper-trading ledger. The in-memory
Portfolio (backend/engine/portfolio.py) remains the per-run book of record
(runner.run applies fills to it directly, unchanged) -- this just mirrors
every order/fill/position snapshot into Mongo so a process restart doesn't
lose history, and so backend/routers/trading.py has something to query.

Same db-handle pattern as backend/database.py (a motor/mongomock-motor
database passed in, not constructed here).
"""

from datetime import datetime
from typing import Optional

from backend.core.models import Fill, Order, Position


class LedgerStore:
    def __init__(self, db) -> None:
        self.orders = db["paper_orders"]
        self.fills = db["paper_fills"]
        self.positions = db["paper_positions"]

    async def record_order(self, order: Order) -> None:
        await self.orders.insert_one(order.model_dump())

    async def record_fill(self, fill: Fill) -> None:
        await self.fills.insert_one(fill.model_dump())

    async def snapshot_positions(self, positions: dict[str, Position]) -> None:
        for symbol, position in positions.items():
            await self.positions.update_one(
                {"symbol": symbol},
                {"$set": position.model_dump()},
                upsert=True,
            )

    async def get_open_positions(self) -> dict[str, Position]:
        cursor = self.positions.find({"quantity": {"$ne": 0}})
        docs = await cursor.to_list(length=None)
        result = {}
        for doc in docs:
            doc.pop("_id", None)
            position = Position(**doc)
            result[position.symbol] = position
        return result

    async def get_fills(
        self, symbol: Optional[str] = None, since: Optional[datetime] = None
    ) -> list[Fill]:
        query: dict = {}
        if symbol is not None:
            query["symbol"] = symbol
        if since is not None:
            query["timestamp"] = {"$gte": since}
        cursor = self.fills.find(query).sort("timestamp", 1)
        docs = await cursor.to_list(length=None)
        fills = []
        for doc in docs:
            doc.pop("_id", None)
            fills.append(Fill(**doc))
        return fills
