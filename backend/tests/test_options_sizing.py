from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Intent, Side
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver
from backend.options.sizing import size_option_intent
from backend.scoring.composite import CompositeScore


class _FakeCtx:
    def __init__(self, closes: list[float], now: datetime) -> None:
        self._closes = closes
        self._now = now

    def history(self, symbol: str, n: int) -> list:
        return [SimpleNamespace(close=c) for c in self._closes[-n:]]

    def now(self) -> datetime:
        return self._now


NOW = datetime(2024, 12, 1, tzinfo=timezone.utc)
CLOSES = [2900.0, 2880.0, 2910.0, 2895.0, 2905.0] * 5  # 25 bars, some variance


def _intent() -> Intent:
    return Intent(
        symbol="RELIANCE", side=Side.SELL, strength=0.8, reason_codes=["oversold_csp"],
        option_flavor="CSP",
    )


def _scored() -> CompositeScore:
    return CompositeScore(rule_score=0.8, ai_score=0.0)


@pytest.fixture
def master():
    return InstrumentMaster(AsyncMongoMockClient()["test_db"])


async def _seed_contract(master, expiry, strike) -> None:
    tradingsymbol = resolver.format_tradingsymbol("RELIANCE", expiry, strike, "PE")
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol=tradingsymbol, name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05, expiry=datetime.combine(expiry, datetime.min.time()), strike=strike,
    )])


@pytest.mark.asyncio
async def test_returns_none_when_master_is_none():
    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, None)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_contract_not_synced(master):
    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, master)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_with_fewer_than_20_bars(master):
    ctx = _FakeCtx(CLOSES[:5], NOW)
    result = await size_option_intent(_intent(), _scored(), ctx, 1_000_000.0, master)
    assert result is None


@pytest.mark.asyncio
async def test_sizes_a_resolved_contract(master):
    expiry = resolver.next_monthly_expiry(NOW.date())
    strike = resolver.nearest_strike("RELIANCE", CLOSES[-1], 0.05)
    await _seed_contract(master, expiry, strike)

    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, master)

    assert result is not None
    assert result.order.symbol == resolver.format_tradingsymbol("RELIANCE", expiry, strike, "PE")
    assert result.order.side == Side.SELL
    assert result.order.product == "NRML"
    assert result.order.quantity % 250.0 == 0
    assert result.order.quantity > 0
    assert result.contract.lot_size == 250
    assert result.premium_estimate >= 0.0
    assert result.margin_estimate > 0.0
    assert result.underlying_spot == CLOSES[-1]


@pytest.mark.asyncio
async def test_returns_none_when_budget_covers_no_lots(master):
    expiry = resolver.next_monthly_expiry(NOW.date())
    strike = resolver.nearest_strike("RELIANCE", CLOSES[-1], 0.05)
    await _seed_contract(master, expiry, strike)

    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), account_size=1.0, master=master)
    assert result is None
