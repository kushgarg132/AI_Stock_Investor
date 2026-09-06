"""Fills -> trades.

The ledger stored orders, fills and position snapshots, but nothing that
answers "which trades are running and which are finished?" -- fills are
executions, not trades, and a position snapshot forgets how it was opened.
LedgerStore.on_fill maintains a `paper_trades` row per round trip so the
dashboard's Active/Completed tables have something real to read.
"""

from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Fill, Order, Position, Side
from backend.engine.persistence import LedgerStore

T0 = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)


def _utc(value: datetime) -> datetime:
    """Mongo stores UTC and hands it back naive, so timestamps read out of
    the ledger need the zone reattached before comparing."""
    return value.replace(tzinfo=timezone.utc)


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


@pytest.fixture
def ledger(mongo):
    return LedgerStore(mongo, user_id="alice", run_id="run-1")


def _fill(side: Side, quantity: float, price: float, minutes: int = 0, order_id: str = "o1") -> Fill:
    return Fill(
        order_id=order_id, symbol="RELIANCE", side=side, quantity=quantity, price=price,
        timestamp=T0 + timedelta(minutes=minutes), costs=1.0,
    )


def _order(order_id: str, side: Side, quantity: float, product: str = "CNC") -> Order:
    return Order(
        id=order_id, symbol="RELIANCE", side=side, quantity=quantity,
        order_type="MARKET", limit_price=None, product=product,
    )


async def _buy_ten(ledger) -> Position:
    """Opens a 10-share long at 100, the starting point for most cases here."""
    position = Position(symbol="RELIANCE", quantity=10.0, avg_price=100.0)
    await ledger.on_fill(_fill(Side.BUY, 10.0, 100.0), quantity_before=0.0, position=position)
    return position


@pytest.mark.asyncio
async def test_first_fill_opens_a_trade(ledger):
    await _buy_ten(ledger)

    trades = await ledger.get_trades()
    assert len(trades) == 1
    trade = trades[0]
    assert trade["status"] == "OPEN"
    assert trade["symbol"] == "RELIANCE"
    assert trade["side"] == "BUY"
    assert trade["quantity"] == 10.0
    assert trade["entry_price"] == 100.0
    assert _utc(trade["entry_at"]) == T0
    assert trade["exit_price"] is None
    assert trade["run_id"] == "run-1"


@pytest.mark.asyncio
async def test_adding_to_a_position_updates_the_same_trade(ledger):
    position = await _buy_ten(ledger)

    # Portfolio's weighted average after buying 5 more at 120.
    position.quantity, position.avg_price = 15.0, (100.0 * 10 + 120.0 * 5) / 15
    await ledger.on_fill(_fill(Side.BUY, 5.0, 120.0, minutes=5), quantity_before=10.0, position=position)

    trades = await ledger.get_trades()
    assert len(trades) == 1, "adding to a position must not open a second trade"
    assert trades[0]["quantity"] == 15.0
    assert trades[0]["entry_price"] == pytest.approx(106.666666, rel=1e-4)
    assert trades[0]["status"] == "OPEN"


@pytest.mark.asyncio
async def test_closing_the_position_closes_the_trade(ledger):
    position = await _buy_ten(ledger)

    position.quantity, position.avg_price, position.realized_pnl = 0.0, 0.0, 250.0
    await ledger.on_fill(_fill(Side.SELL, 10.0, 125.0, minutes=60), quantity_before=10.0, position=position)

    trade = (await ledger.get_trades())[0]
    assert trade["status"] == "CLOSED"
    assert trade["exit_price"] == 125.0
    assert _utc(trade["exit_at"]) == T0 + timedelta(minutes=60)
    assert trade["realized_pnl"] == 250.0
    assert trade["quantity"] == 10.0, "quantity is what was traded, not what is left"


@pytest.mark.asyncio
async def test_partial_exit_keeps_the_trade_open(ledger):
    position = await _buy_ten(ledger)

    position.quantity, position.realized_pnl = 6.0, 60.0
    await ledger.on_fill(_fill(Side.SELL, 4.0, 115.0, minutes=30), quantity_before=10.0, position=position)

    trade = (await ledger.get_trades())[0]
    assert trade["status"] == "OPEN"
    assert trade["quantity"] == 6.0
    assert trade["realized_pnl"] == 60.0


@pytest.mark.asyncio
async def test_a_new_position_after_a_close_is_a_new_trade(ledger):
    position = await _buy_ten(ledger)
    position.quantity, position.realized_pnl = 0.0, 250.0
    await ledger.on_fill(_fill(Side.SELL, 10.0, 125.0, minutes=60), quantity_before=10.0, position=position)

    position.quantity, position.avg_price = 3.0, 130.0
    await ledger.on_fill(_fill(Side.BUY, 3.0, 130.0, minutes=90), quantity_before=0.0, position=position)

    assert len(await ledger.get_trades()) == 2
    assert len(await ledger.get_trades(status="OPEN")) == 1
    assert len(await ledger.get_trades(status="CLOSED")) == 1


@pytest.mark.asyncio
async def test_mode_comes_from_the_order_product(ledger):
    """MIS is the intraday product, CNC the delivery one -- that's what
    separates the two tabs in the UI."""
    await ledger.record_order(_order("intraday-1", Side.BUY, 10.0, product="MIS"))
    position = Position(symbol="RELIANCE", quantity=10.0, avg_price=100.0)
    await ledger.on_fill(
        _fill(Side.BUY, 10.0, 100.0, order_id="intraday-1"), quantity_before=0.0, position=position
    )

    assert (await ledger.get_trades())[0]["mode"] == "INTRADAY"


@pytest.mark.asyncio
async def test_on_fill_also_records_the_fill_and_marks_the_order_filled(ledger, mongo):
    await ledger.record_order(_order("o1", Side.BUY, 10.0))
    position = Position(symbol="RELIANCE", quantity=10.0, avg_price=100.0)
    await ledger.on_fill(_fill(Side.BUY, 10.0, 100.0), quantity_before=0.0, position=position)

    assert len(await ledger.get_fills()) == 1
    assert (await mongo["paper_orders"].find_one({"id": "o1"}))["status"] == "FILLED"


@pytest.mark.asyncio
async def test_trades_are_isolated_per_user(mongo):
    alice = LedgerStore(mongo, user_id="alice")
    bob = LedgerStore(mongo, user_id="bob")
    await _buy_ten(alice)

    assert len(await alice.get_trades()) == 1
    assert await bob.get_trades() == []
