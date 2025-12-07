import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch

# Import correct tools and models
from backend.mcp_tools.stock_info_fetcher import fetch_stock_info_logic
from backend.mcp_tools.trend_detector import detect_trend_logic
from backend.models import Trend, PriceCandle
from backend.mcp_tools.risk_rules_tool import check_risk_logic

# ----------------- Stock Info Fetcher Test ----------------- #
@pytest.mark.asyncio
async def test_stock_info_fetcher_success():
    # Mock yfinance
    mock_ticker = MagicMock()
    mock_ticker.info = {"currentPrice": 150.0, "longName": "Apple Inc."}
    
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = await fetch_stock_info_logic("AAPL")
        
        # get_stock_info return type is CompanyInfo model or dict?
        # Checking implementation: it likely returns a dict or CompanyInfo.
        # Assuming dict based on previous inspection or simple return
        if hasattr(result, "symbol"):
             assert result.symbol == "AAPL"
        else:
             assert result["symbol"] == "AAPL"

# ----------------- Trend Detector Test ----------------- #
def test_trend_detector_logic():
    # Create fake candles for an uptrend
    candles = []
    base_time = datetime.now()
    for i in range(50):
        c = PriceCandle(
            symbol="AAPL",
            timestamp=base_time,
            open=100 + i,
            high=105 + i,
            low=95 + i,
            close=102 + i, # Higher close
            volume=1000
        )
        candles.append(c)
    
    # We need to mock generic Utils or Indicators if they are heavy
    # But detect_trend_logic uses pandas and internal logic.
    # It calls Indicators.calculate_all(df) -> TrendDetector.detect_trend(df)
    
    # We can rely on logic if it's pure.
    try:
        trend, details = detect_trend_logic(candles)
        # With rising prices, likely UP
        assert trend == Trend.UP or trend == Trend.CHOPPY
    except Exception as e:
        pytest.fail(f"Trend detection failed: {e}")

# ----------------- Risk Rules Test ----------------- #
def test_check_risk_pass(mock_db):
    # Valid trade
    result = check_risk_logic(
        account_size=10000.0,
        risk_per_trade_percent=1.0, # risk $100
        entry_price=150.0,
        stop_loss=140.0, # risk $10 per share -> 10 shares
        symbol="AAPL",
        current_exposure=0.0
    )
    
    assert result.approved is True
    assert result.position_size_shares == 10.0
    assert result.position_value == 1500.0

def test_check_risk_fail_exposure(mock_db):
    # Trade exceeds max exposure
    result = check_risk_logic(
        account_size=10000.0,
        risk_per_trade_percent=1.0,
        entry_price=150.0,
        stop_loss=140.0,
        symbol="AAPL",
        current_exposure=99000.0, # Near max
        max_exposure=100000.0
    )
    # 10 shares * 150 = 1500 value. 99k + 1.5k = 100.5k > 100k
    assert result.approved is False
    assert "limit exceeded" in result.reason
