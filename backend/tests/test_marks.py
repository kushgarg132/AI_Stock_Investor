"""Mark prices are best-effort.

The P&L cards are the first thing read on the statement, so a slow or broken
quote provider must cost the unrealised line and nothing else. An absent mark
is already treated as "no mark" downstream; a hung request would instead stall
the whole page.
"""

import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend import marks
from backend.instruments.models import Instrument


def _instrument(symbol: str) -> Instrument:
    return Instrument(
        exchange="NSE", tradingsymbol=symbol, name=symbol, instrument_token=abs(hash(symbol)) % 99999,
        exchange_token=1, instrument_type="EQ", segment="NSE", lot_size=1, tick_size=0.05,
    )


class _Master:
    def __init__(self, _db):
        pass

    async def get(self, exchange, tradingsymbol):
        return _instrument(tradingsymbol)


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


@pytest.mark.asyncio
async def test_quotes_are_returned_per_symbol(mongo, monkeypatch):
    class _Provider:
        async def quote(self, instrument):
            return {"last_price": 101.5}

    monkeypatch.setattr(marks, "InstrumentMaster", _Master)
    monkeypatch.setattr(marks, "YFinanceProvider", _Provider)

    assert await marks.mark_prices(mongo, ["RELIANCE", "TCS"]) == {
        "RELIANCE": 101.5,
        "TCS": 101.5,
    }


@pytest.mark.asyncio
async def test_a_failing_symbol_is_omitted_not_zeroed(mongo, monkeypatch):
    class _Provider:
        async def quote(self, instrument):
            if instrument.tradingsymbol == "TCS":
                raise RuntimeError("provider said no")
            return {"last_price": 101.5}

    monkeypatch.setattr(marks, "InstrumentMaster", _Master)
    monkeypatch.setattr(marks, "YFinanceProvider", _Provider)

    assert await marks.mark_prices(mongo, ["RELIANCE", "TCS"]) == {"RELIANCE": 101.5}


@pytest.mark.asyncio
async def test_a_hanging_provider_gives_up_rather_than_stalling(mongo, monkeypatch):
    class _Provider:
        async def quote(self, instrument):
            await asyncio.sleep(30)

    monkeypatch.setattr(marks, "InstrumentMaster", _Master)
    monkeypatch.setattr(marks, "YFinanceProvider", _Provider)
    monkeypatch.setattr(marks, "TIMEOUT_SECONDS", 0.05)

    assert await asyncio.wait_for(marks.mark_prices(mongo, ["RELIANCE"]), timeout=2) == {}


@pytest.mark.asyncio
async def test_no_symbols_makes_no_calls(mongo, monkeypatch):
    class _Provider:
        async def quote(self, instrument):
            raise AssertionError("should not be called")

    monkeypatch.setattr(marks, "InstrumentMaster", _Master)
    monkeypatch.setattr(marks, "YFinanceProvider", _Provider)

    assert await marks.mark_prices(mongo, []) == {}
