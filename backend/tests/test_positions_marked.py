"""GET /trading/positions marks positions to market.

The stored Position document's unrealized_pnl is never updated after it is
first written -- the engine loop only ever writes 0.0 there -- so a route
that returned it unmarked would show every open position as flat regardless
of the real price, which is exactly the number a person opens this page to
check.
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Position
from backend.engine.persistence import LedgerStore
from backend.routers import trading


@pytest.fixture
def ledger():
    client = AsyncMongoMockClient()
    return LedgerStore(client["test_db"], user_id="u1")


@pytest.fixture
def client(ledger, monkeypatch):
    async def fake_marks(db, symbols):
        return {"RELIANCE": 1500.0}

    monkeypatch.setattr(trading, "mark_prices", fake_marks)

    app = FastAPI()
    app.include_router(trading.router, prefix="/api/v1")
    app.dependency_overrides[trading.get_ledger_store] = lambda: ledger
    return TestClient(app)


def test_open_positions_are_marked_to_the_live_quote(client, ledger):
    asyncio.run(ledger.snapshot_positions({
        "RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=1400.0, realized_pnl=500.0),
    }))

    body = client.get("/api/v1/trading/positions").json()

    assert body["RELIANCE"]["unrealized_pnl"] == pytest.approx(1000.0)
    assert body["RELIANCE"]["realized_pnl"] == 500.0, "realized P&L must not be touched by marking"


def test_a_symbol_with_no_quote_reports_zero_movement_not_a_crash(client, ledger):
    asyncio.run(ledger.snapshot_positions({
        "UNKNOWN": Position(symbol="UNKNOWN", quantity=5.0, avg_price=100.0),
    }))

    body = client.get("/api/v1/trading/positions").json()

    assert body["UNKNOWN"]["unrealized_pnl"] == 0.0
