"""Per-user scoping of the paper-trading ledger.

Before this, paper_orders/paper_fills/paper_positions carried no user_id, so
every signed-in account shared one book -- any P&L figure built on it mixed
users together. These tests pin the isolation: two LedgerStores over the same
Mongo database, one per user, must never see each other's rows.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Fill, Order, Position, Side
from backend.engine.persistence import LedgerStore
from backend.runs import RunStore


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


def _fill(order_id: str, symbol: str) -> Fill:
    return Fill(
        order_id=order_id, symbol=symbol, side=Side.BUY, quantity=1.0, price=100.0,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), costs=1.0,
    )


def _order(order_id: str, symbol: str) -> Order:
    return Order(
        id=order_id, symbol=symbol, side=Side.BUY, quantity=1.0,
        order_type="MARKET", limit_price=None, product="CNC",
    )


@pytest.mark.asyncio
async def test_positions_are_isolated_per_user(mongo):
    alice = LedgerStore(mongo, user_id="alice")
    bob = LedgerStore(mongo, user_id="bob")

    await alice.snapshot_positions({"RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=2500.0)})
    await bob.snapshot_positions({"TCS": Position(symbol="TCS", quantity=5.0, avg_price=3500.0)})

    assert set(await alice.get_open_positions()) == {"RELIANCE"}
    assert set(await bob.get_open_positions()) == {"TCS"}


@pytest.mark.asyncio
async def test_same_symbol_two_users_do_not_overwrite_each_other(mongo):
    """The positions upsert key used to be {symbol} alone, so two users
    holding the same stock clobbered one another's quantity."""
    alice = LedgerStore(mongo, user_id="alice")
    bob = LedgerStore(mongo, user_id="bob")

    await alice.snapshot_positions({"RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=2500.0)})
    await bob.snapshot_positions({"RELIANCE": Position(symbol="RELIANCE", quantity=3.0, avg_price=2400.0)})

    assert (await alice.get_open_positions())["RELIANCE"].quantity == 10.0
    assert (await bob.get_open_positions())["RELIANCE"].quantity == 3.0


@pytest.mark.asyncio
async def test_fills_are_isolated_per_user(mongo):
    alice = LedgerStore(mongo, user_id="alice")
    bob = LedgerStore(mongo, user_id="bob")

    await alice.record_fill(_fill("o1", "RELIANCE"))
    await bob.record_fill(_fill("o2", "TCS"))

    assert [f.symbol for f in await alice.get_fills()] == ["RELIANCE"]
    assert [f.symbol for f in await bob.get_fills()] == ["TCS"]


@pytest.mark.asyncio
async def test_orders_are_stamped_with_user_and_run(mongo):
    ledger = LedgerStore(mongo, user_id="alice", run_id="run-1")
    await ledger.record_order(_order("o1", "RELIANCE"))

    doc = await mongo["paper_orders"].find_one({"id": "o1"})
    assert doc["user_id"] == "alice"
    assert doc["run_id"] == "run-1"


@pytest.mark.asyncio
async def test_mark_filled_moves_order_out_of_pending(mongo):
    """Order.status was written once as PENDING and never updated, so the
    orders collection could not answer 'did this actually execute?'."""
    ledger = LedgerStore(mongo, user_id="alice")
    await ledger.record_order(_order("o1", "RELIANCE"))
    assert (await mongo["paper_orders"].find_one({"id": "o1"}))["status"] == "PENDING"

    await ledger.mark_filled("o1")
    assert (await mongo["paper_orders"].find_one({"id": "o1"}))["status"] == "FILLED"


@pytest.mark.asyncio
async def test_get_orders_is_scoped_and_newest_first(mongo):
    alice = LedgerStore(mongo, user_id="alice")
    bob = LedgerStore(mongo, user_id="bob")
    await alice.record_order(_order("o1", "RELIANCE"))
    await bob.record_order(_order("o2", "TCS"))

    assert [o.id for o in await alice.get_orders()] == ["o1"]


# ---------------------------------------------------------------------------
# RunStore -- runs must survive a process restart, unlike the in-memory _RUNS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_lifecycle_is_persisted(mongo):
    runs = RunStore(mongo)
    await runs.create(run_id="r1", user_id="alice", mode="LONGTERM", universe=["RELIANCE"], params={})

    active = await runs.list_active("alice")
    assert [r["run_id"] for r in active] == ["r1"]

    await runs.mark_stopped("r1")
    assert await runs.list_active("alice") == []


@pytest.mark.asyncio
async def test_runs_are_isolated_per_user(mongo):
    runs = RunStore(mongo)
    await runs.create(run_id="r1", user_id="alice", mode="LONGTERM", universe=[], params={})
    await runs.create(run_id="r2", user_id="bob", mode="INTRADAY", universe=[], params={})

    assert [r["run_id"] for r in await runs.list_active("bob")] == ["r2"]


@pytest.mark.asyncio
async def test_orphaned_runs_are_closed_on_startup(mongo):
    """_RUNS is a process-global dict of asyncio.Tasks; a restart loses every
    task but left the Mongo row saying RUNNING forever."""
    runs = RunStore(mongo)
    await runs.create(run_id="r1", user_id="alice", mode="LONGTERM", universe=[], params={})

    closed = await runs.close_orphaned()

    assert closed == 1
    assert await runs.list_active("alice") == []
    assert (await mongo["trading_runs"].find_one({"run_id": "r1"}))["error"] == "orphaned by restart"


@pytest.mark.asyncio
async def test_mark_error_records_the_reason(mongo):
    runs = RunStore(mongo)
    await runs.create(run_id="r1", user_id="alice", mode="LONGTERM", universe=[], params={})

    await runs.mark_error("r1", "feed exploded")

    doc = await mongo["trading_runs"].find_one({"run_id": "r1"})
    assert doc["status"] == "ERROR"
    assert doc["error"] == "feed exploded"


def test_asyncio_run_still_works_for_sync_callers(mongo):
    """Guards the sync-fixture style used by backend/tests/test_trading_router.py."""
    ledger = LedgerStore(mongo, user_id="alice")
    asyncio.run(ledger.record_fill(_fill("o1", "RELIANCE")))
    assert len(asyncio.run(ledger.get_fills())) == 1
