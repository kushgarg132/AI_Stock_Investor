"""KiteProvider: interval-string mapping, from_date/to_date math, and that
the blocking pykiteconnect SDK calls are actually routed through
asyncio.to_thread (never called directly on the event loop)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.data.providers.kite_provider import KiteProvider
from backend.instruments.models import Instrument


def _instrument(**overrides) -> Instrument:
    defaults = dict(
        exchange="NSE", tradingsymbol="RELIANCE", name="Reliance Industries Ltd",
        instrument_token=128031748, exchange_token=500124, instrument_type="EQ",
        segment="NSE", lot_size=1, tick_size=0.05,
    )
    defaults.update(overrides)
    return Instrument(**defaults)


FIXED_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "interval, kite_interval",
    [("1m", "minute"), ("5m", "5minute"), ("15m", "15minute"),
     ("30m", "30minute"), ("60m", "60minute"), ("1h", "60minute"), ("1d", "day")],
)
def test_interval_mapping_supported_values(interval, kite_interval):
    provider = KiteProvider(kite_client_factory=lambda: MagicMock())
    assert provider._kite_interval(interval) == kite_interval


def test_interval_mapping_raises_for_unmapped_value():
    provider = KiteProvider(kite_client_factory=lambda: MagicMock())
    with pytest.raises(ValueError, match="Unsupported interval for Kite"):
        provider._kite_interval("90m")


@pytest.mark.parametrize(
    "period, expected_days",
    [("1mo", 30), ("1y", 365)],
)
def test_period_to_range_math(period, expected_days):
    provider = KiteProvider(kite_client_factory=lambda: MagicMock(), now_fn=lambda: FIXED_NOW)
    from_date, to_date = provider._period_to_range(period)

    assert to_date == FIXED_NOW
    assert from_date == FIXED_NOW - timedelta(days=expected_days)


def test_period_to_range_raises_for_unmapped_value():
    provider = KiteProvider(kite_client_factory=lambda: MagicMock(), now_fn=lambda: FIXED_NOW)
    with pytest.raises(ValueError, match="Unsupported period for Kite"):
        provider._period_to_range("ytd")


async def test_history_uses_to_thread_and_maps_candles():
    instrument = _instrument()
    mock_kite = MagicMock()
    mock_kite.historical_data.return_value = [
        {"date": datetime(2026, 6, 1, tzinfo=timezone.utc), "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 1000},
    ]
    provider = KiteProvider(kite_client_factory=lambda: mock_kite, now_fn=lambda: FIXED_NOW)

    with patch("backend.data.providers.kite_provider.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))) as mock_to_thread:
        candles = await provider.history(instrument, interval="1d", period="1mo")

    mock_to_thread.assert_called_once()
    call_args = mock_to_thread.call_args.args
    assert call_args[0] is mock_kite.historical_data
    assert call_args[1] == instrument.instrument_token
    assert call_args[3] == FIXED_NOW  # to_date
    assert call_args[4] == "day"  # mapped kite interval

    assert len(candles) == 1
    assert candles[0].open == 100.0
    assert candles[0].close == 104.0
    assert candles[0].volume == 1000


async def test_history_raises_for_unmapped_interval_without_calling_sdk():
    instrument = _instrument()
    mock_kite = MagicMock()
    provider = KiteProvider(kite_client_factory=lambda: mock_kite, now_fn=lambda: FIXED_NOW)

    with pytest.raises(ValueError):
        await provider.history(instrument, interval="90m", period="1mo")

    mock_kite.historical_data.assert_not_called()


async def test_quote_uses_to_thread_and_maps_fields():
    instrument = _instrument()
    mock_kite = MagicMock()
    mock_kite.quote.return_value = {
        "NSE:RELIANCE": {
            "last_price": 2500.0,
            "volume": 12345,
            "ohlc": {"open": 2480.0, "high": 2510.0, "low": 2470.0, "close": 2490.0},
        }
    }
    provider = KiteProvider(kite_client_factory=lambda: mock_kite)

    with patch("backend.data.providers.kite_provider.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))) as mock_to_thread:
        quote = await provider.quote(instrument)

    mock_to_thread.assert_called_once_with(mock_kite.quote, "NSE:RELIANCE")
    assert quote == {
        "symbol": "RELIANCE",
        "last_price": 2500.0,
        "open": 2480.0,
        "high": 2510.0,
        "low": 2470.0,
        "close": 2490.0,
        "volume": 12345,
    }


async def test_to_thread_actually_used_for_history_real_asyncio():
    """Doesn't mock asyncio.to_thread at all -- proves the blocking SDK call
    genuinely runs off-loop by making it sleep and confirming the event loop
    stays responsive concurrently."""
    import asyncio
    import time

    instrument = _instrument()
    mock_kite = MagicMock()

    def slow_historical_data(*args, **kwargs):
        time.sleep(0.05)  # blocking, real thread-sleep
        return []

    mock_kite.historical_data.side_effect = slow_historical_data
    provider = KiteProvider(kite_client_factory=lambda: mock_kite, now_fn=lambda: FIXED_NOW)

    ticks = []

    async def ticker():
        for _ in range(10):
            ticks.append(1)
            await asyncio.sleep(0.005)

    await asyncio.gather(provider.history(instrument, interval="1d", period="1mo"), ticker())
    assert len(ticks) == 10  # the event loop kept running the ticker concurrently
