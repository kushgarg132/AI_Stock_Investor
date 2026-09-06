"""/suggestions/* -- the approve/reject inbox.

Approving is the only place in the app where a human causes a trade, so the
guards matter more than the happy path: no double execution, no acting on
someone else's inbox, and an approval that actually reaches the ledger.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.auth.dependency import get_current_user
from backend.auth.models import User
from backend.core.models import Intent, Order, Side
from backend.engine.persistence import LedgerStore
from backend.engine.runner import Proposal
from backend.routers import suggestions as suggestions_router
from backend.scoring.composite import CompositeScore
from backend.suggestions.store import SuggestionStore

_USER = User(
    id="alice", google_sub="sub-1", email="alice@example.com", name="Alice",
    picture=None, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
)


def _proposal(symbol: str = "RELIANCE", mode: str = "LONGTERM") -> Proposal:
    return Proposal(
        order=Order(
            id="o-seed", symbol=symbol, side=Side.BUY, quantity=10.0,
            order_type="MARKET", limit_price=None, product="CNC",
        ),
        intent=Intent(
            symbol=symbol, side=Side.BUY, strength=0.9, reason_codes=["macd_cross"],
            stop_hint=90.0, target_hint=140.0,
        ),
        score=CompositeScore(rule_score=0.9, ai_score=0.2),
        entry=100.0,
        mode=mode,
    )


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


@pytest.fixture
def store(mongo):
    return SuggestionStore(mongo)


@pytest.fixture
def ledger(mongo):
    return LedgerStore(mongo, user_id="alice")


@pytest.fixture
def client(store, ledger):
    app = FastAPI()
    app.include_router(suggestions_router.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[suggestions_router.get_suggestion_store] = lambda: store
    app.dependency_overrides[suggestions_router.get_ledger_store] = lambda: ledger
    # No yfinance round trip in a unit test: approving fills at this price.
    app.dependency_overrides[suggestions_router.get_mark_price] = lambda: _fake_mark_price
    return TestClient(app)


async def _fake_mark_price(symbol: str) -> float:
    return 105.0


async def _seed(store, **overrides) -> dict:
    payload = dict(user_id="alice", proposal=_proposal(), source="scheduler")
    payload.update(overrides)
    return await store.create(**payload)


def test_list_returns_the_users_pending_inbox(client, store):
    import asyncio
    asyncio.run(_seed(store))
    asyncio.run(_seed(store, proposal=_proposal(symbol="TCS", mode="INTRADAY")))

    resp = client.get("/api/v1/suggestions", params={"mode": "LONGTERM"})

    assert resp.status_code == 200
    body = resp.json()
    assert [s["symbol"] for s in body] == ["RELIANCE"]
    assert body[0]["reason_codes"] == ["macd_cross"]
    assert body[0]["score"]["final"] > 0


def test_approve_places_the_order_and_opens_a_trade(client, store, ledger):
    import asyncio
    suggestion = asyncio.run(_seed(store))

    resp = client.post(f"/api/v1/suggestions/{suggestion['id']}/approve")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "EXECUTED"
    assert body["order_id"]

    trades = asyncio.run(ledger.get_trades())
    assert len(trades) == 1
    assert trades[0]["symbol"] == "RELIANCE"
    assert trades[0]["quantity"] == 10.0
    assert trades[0]["entry_price"] == 105.0, "fills at the current mark, not the stale reference"
    assert trades[0]["status"] == "OPEN"

    positions = asyncio.run(ledger.get_open_positions())
    assert positions["RELIANCE"].quantity == 10.0


def test_approving_twice_does_not_place_a_second_order(client, store, ledger):
    import asyncio
    suggestion = asyncio.run(_seed(store))

    first = client.post(f"/api/v1/suggestions/{suggestion['id']}/approve")
    second = client.post(f"/api/v1/suggestions/{suggestion['id']}/approve")

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(asyncio.run(ledger.get_trades())) == 1


def test_reject_decides_without_touching_the_ledger(client, store, ledger):
    import asyncio
    suggestion = asyncio.run(_seed(store))

    resp = client.post(f"/api/v1/suggestions/{suggestion['id']}/reject", json={"reason": "too extended"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"
    assert resp.json()["reason"] == "too extended"
    assert asyncio.run(ledger.get_trades()) == []


def test_cannot_act_on_another_users_suggestion(client, store):
    import asyncio
    suggestion = asyncio.run(_seed(store, user_id="bob"))

    assert client.post(f"/api/v1/suggestions/{suggestion['id']}/approve").status_code == 404
    assert client.post(f"/api/v1/suggestions/{suggestion['id']}/reject").status_code == 404
