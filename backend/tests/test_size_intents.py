"""backend.engine.runner.size_intents: real scoring + risk sizing wired in
place of Task 4's stub. Covers the two properties the brief requires
regardless of the exact conviction-to-size formula:
- a lower scored.final must never produce a larger position than a higher
  one, all else equal (monotonicity);
- an Intent whose rule floor wasn't met produces zero orders, full stop.
Plus the exposure-limit rejection and missing-stop_hint skip paths.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.core.models import Intent, Position, Side
from backend.engine.portfolio import Portfolio
from backend.engine.runner import size_intents


class _FakeCtx:
    """Minimal StrategyContext stand-in: only `history()` is used by
    size_intents, to look up the current price for an Intent's symbol."""

    def __init__(self, prices: dict[str, float]) -> None:
        self._prices = prices

    def history(self, symbol: str, n: int) -> list:
        if symbol not in self._prices:
            return []
        return [SimpleNamespace(close=self._prices[symbol])]


class _FakeStrategy:
    def __init__(self, mode: str, name: str = "fake") -> None:
        self.spec = SimpleNamespace(mode=mode, name=name)


def _no_sentiment_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    return redis


@pytest.mark.asyncio
async def test_rule_floor_not_met_produces_zero_orders_regardless_of_ai():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.1,  # below RULE_FLOOR=0.45
        reason_codes=["weak_signal"], stop_hint=90.0,
    )
    redis = AsyncMock()
    redis.get.return_value = "1.0"  # maximum possible AI sentiment

    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, redis,
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert orders == []


@pytest.mark.asyncio
async def test_no_stop_hint_produces_no_order_not_a_crash():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.9,
        reason_codes=["strong_signal"],  # no stop_hint
    )
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert orders == []


@pytest.mark.asyncio
async def test_higher_scored_final_never_produces_a_smaller_position():
    async def size_for(strength: float) -> float:
        intent = Intent(
            symbol="RELIANCE", side=Side.BUY, strength=strength,
            reason_codes=["signal"], stop_hint=90.0,
        )
        orders = await size_intents(
            [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
            account_size=1_000_000.0, max_exposure=1_000_000.0,
        )
        assert len(orders) == 1
        return orders[0].quantity

    low_size = await size_for(0.5)   # just above RULE_FLOOR
    high_size = await size_for(1.0)  # maximum conviction
    assert high_size >= low_size
    assert high_size > low_size  # strictly, since the formula is strictly increasing


@pytest.mark.asyncio
async def test_exposure_limit_rejects_when_new_position_would_exceed_max():
    portfolio = Portfolio()
    portfolio.positions["TCS"] = Position(symbol="TCS", quantity=100.0, avg_price=3000.0)
    # existing exposure = 300,000; max_exposure just under that + anything new
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.9,
        reason_codes=["signal"], stop_hint=90.0,
    )
    orders = await size_intents(
        [intent], portfolio, _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=300_000.0,
    )
    assert orders == []


@pytest.mark.asyncio
async def test_product_is_mis_for_intraday_strategy_and_cnc_otherwise():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.9,
        reason_codes=["signal"], stop_hint=90.0,
    )
    ctx = _FakeCtx({"RELIANCE": 100.0})

    intraday_orders = await size_intents(
        [intent], Portfolio(), ctx, {"RELIANCE": _FakeStrategy("INTRADAY")}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert intraday_orders[0].product == "MIS"

    longterm_orders = await size_intents(
        [intent], Portfolio(), ctx, {"RELIANCE": _FakeStrategy("LONGTERM")}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert longterm_orders[0].product == "CNC"


# ---------------------------------------------------------------------------
# Phase 3 safety rails: per-trade capital cap, kill-switch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_trade_cap_rejects_a_trade_whose_notional_exceeds_it():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=1.0,
        reason_codes=["signal"], stop_hint=90.0,
    )
    # Full-conviction sizing against a ₹1,000,000 account would normally
    # produce a notional far above a ₹5,000 per-trade cap.
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, per_trade_cap=5_000.0,
    )
    assert orders == []


@pytest.mark.asyncio
async def test_per_trade_cap_allows_a_trade_within_it():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=1.0,
        reason_codes=["signal"], stop_hint=99.0,  # tight stop -> small size
    )
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, per_trade_cap=10_000_000.0,
    )
    assert len(orders) == 1


@pytest.mark.asyncio
async def test_no_per_trade_cap_means_no_extra_limit():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=1.0,
        reason_codes=["signal"], stop_hint=90.0,
    )
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}), {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,  # per_trade_cap omitted
    )
    assert len(orders) == 1


@pytest.mark.asyncio
async def test_a_tripped_kill_switch_blocks_intraday_orders():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.9,
        reason_codes=["signal"], stop_hint=90.0,
    )
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}),
        {"RELIANCE": _FakeStrategy("INTRADAY")}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, kill_switch_tripped=True,
    )
    assert orders == []


@pytest.mark.asyncio
async def test_a_tripped_kill_switch_does_not_block_longterm_suggestions():
    """The kill-switch is about auto-executed risk. Long-term proposals stop
    at a human-approved suggestion regardless, so blocking them too would
    only hide information from the person reviewing the inbox."""
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=0.9,
        reason_codes=["signal"], stop_hint=90.0,
    )
    orders = await size_intents(
        [intent], Portfolio(), _FakeCtx({"RELIANCE": 100.0}),
        {"RELIANCE": _FakeStrategy("LONGTERM")}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, kill_switch_tripped=True,
    )
    assert len(orders) == 1


@pytest.mark.asyncio
async def test_order_carries_the_owning_strategys_name():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=1.0,
        reason_codes=["signal"], stop_hint=90.0,
    )
    ctx = _FakeCtx({"RELIANCE": 100.0})
    strategy = _FakeStrategy(mode="INTRADAY", name="volume_surge")
    orders = await size_intents(
        [intent], Portfolio(), ctx, {"RELIANCE": strategy}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert len(orders) == 1
    assert orders[0].strategy_name == "volume_surge"


def test_order_strategy_name_defaults_to_none():
    from backend.core.models import Order, Side
    order = Order(id="x", symbol="RELIANCE", side=Side.BUY, quantity=1.0, order_type="MARKET")
    assert order.strategy_name is None
