from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

import yfinance as yf
import pandas as pd
from backend.models import PriceCandle

logger = logging.getLogger(__name__)

router = APIRouter()

class PriceHistoryRequest(BaseModel):
    symbol: str
    period: str = "1mo" # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: str = "1d" # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

class PriceHistoryResponse(BaseModel):
    symbol: str
    candles: List[PriceCandle]
    source: str = "yfinance"  # Track data source

@router.post("/price_history", response_model=PriceHistoryResponse)
async def fetch_price_history(request: PriceHistoryRequest):
    """
    Fetches historical price data for a given symbol.
    Uses yfinance with smart suffix resolution (US, NSE, BSE).
    """
    candles, source = await fetch_price_history_logic(request.symbol, request.period, request.interval)
    return PriceHistoryResponse(symbol=request.symbol, candles=candles, source=source)

async def fetch_price_history_logic(symbol: str, period: str = "1mo", interval: str = "1d") -> tuple[List[PriceCandle], str]:
    """
    Core logic for fetching price history.
    """
    logger.info(f"Fetching price history for {symbol}, period: {period}, interval: {interval}")
    
    source = "yfinance"
    
    # Try multiple suffixes: original, NSE, BSE
    suffixes = ["", ".NS", ".BO"]
    
    for suffix in suffixes:
        try_symbol = f"{symbol}{suffix}"
        
        try:
            ticker = yf.Ticker(try_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if not df.empty:
                logger.info(f"Retrieved {len(df)} candles for {try_symbol}")
                
                 # Process and return data
                candles = []
                for index, row in df.iterrows():
                    # Handle different index types
                    if isinstance(index, datetime):
                        ts = index
                    elif hasattr(index, 'to_pydatetime'):
                        ts = index.to_pydatetime()
                    else:
                        ts = pd.to_datetime(index)
                    
                    candles.append(PriceCandle(
                        symbol=try_symbol.upper(),
                        timestamp=ts,
                        open=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        adj_close=float(row.get('Adj Close', row['Close'])),
                        volume=int(row.get('Volume', 0))
                    ))
                    
                logger.info(f"Price history fetch complete for {try_symbol} via {source}. Returning {len(candles)} candles")
                return candles, source
                
            else:
                 logger.debug(f"No price data for {try_symbol}, trying next suffix...")
        
        except Exception as e:
            logger.debug(f"Error fetching price history for {try_symbol}: {e}")
            continue

    # If all fail
    logger.error(f"Failed to fetch price history for {symbol} after trying suffixes {suffixes}")
    raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol} (tried suffixes: {suffixes})")

@router.get("/price_history/test")
async def test_fetcher():
    """Test endpoint to verify data source connectivity"""
    results = {}
    
    # Test yfinance
    try:
        ticker = yf.Ticker("AAPL")
        hist = ticker.history(period="1d")
        results["yfinance"] = {"status": "ok", "symbol": "AAPL", "last_price": float(hist['Close'].iloc[-1])}
    except Exception as e:
        results["yfinance"] = {"status": "error", "detail": str(e)}
    
    return results
