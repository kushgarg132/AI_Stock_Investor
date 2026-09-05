"""Tests for YFinanceProvider: it must derive the yfinance ticker
deterministically from an already-resolved Instrument's exchange, with no
suffix guessing anywhere in the call path."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.data.providers.yfinance_provider import YFinanceProvider
from backend.instruments.models import Instrument

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _instrument(exchange="NSE", tradingsymbol="RELIANCE") -> Instrument:
    return Instrument(
        exchange=exchange, tradingsymbol=tradingsymbol, name="Reliance Industries Ltd",
        instrument_token=1, exchange_token=1, instrument_type="EQ", segment="NSE",
        lot_size=1, tick_size=0.05,
    )


def _fake_history_df():
    return pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [102.0, 103.0],
        "Low": [99.0, 100.0],
        "Close": [101.0, 102.0],
        "Volume": [1000, 1100],
    }, index=pd.to_datetime(["2026-01-01", "2026-01-02"]))


async def test_history_uses_ns_suffix_for_nse():
    provider = YFinanceProvider()
    instrument = _instrument(exchange="NSE", tradingsymbol="RELIANCE")

    with patch("backend.data.providers.yfinance_provider.yf.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _fake_history_df()
        mock_ticker_cls.return_value = mock_ticker

        candles = await provider.history(instrument, interval="1d", period="1mo")

        mock_ticker_cls.assert_called_once_with("RELIANCE.NS")
        assert len(candles) == 2
        assert candles[0].symbol == "RELIANCE.NS"


async def test_history_uses_bo_suffix_for_bse():
    provider = YFinanceProvider()
    instrument = _instrument(exchange="BSE", tradingsymbol="RELIANCE")

    with patch("backend.data.providers.yfinance_provider.yf.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _fake_history_df()
        mock_ticker_cls.return_value = mock_ticker

        await provider.history(instrument, interval="1d", period="1mo")

        mock_ticker_cls.assert_called_once_with("RELIANCE.BO")


async def test_history_raises_on_empty_data():
    provider = YFinanceProvider()
    instrument = _instrument()

    with patch("backend.data.providers.yfinance_provider.yf.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        with pytest.raises(ValueError):
            await provider.history(instrument, interval="1d", period="1mo")


async def test_unsupported_exchange_raises():
    provider = YFinanceProvider()
    instrument = _instrument(exchange="NYSE", tradingsymbol="AAPL")

    with pytest.raises(ValueError):
        await provider.history(instrument, interval="1d", period="1mo")


def test_no_suffix_loop_in_price_and_stock_info_source():
    """Regression guard: the [".NS", ".BO"] brute-force loop that used to try
    suffixes one by one until something stuck must not reappear."""
    for rel_path in ("components/quant/price.py", "components/master/stock_info.py"):
        source = (_BACKEND_DIR / rel_path).read_text()
        assert '".NS", ".BO"' not in source
        assert "suffixes = [" not in source
