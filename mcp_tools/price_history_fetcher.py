from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
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

@router.post("/price_history", response_model=PriceHistoryResponse)
async def fetch_price_history(request: PriceHistoryRequest):
    """
    Fetches historical price data for a given symbol using yfinance.
    """
    logger.info(f"Fetching price history for {request.symbol}, period: {request.period}, interval: {request.interval}")
    try:
        # Fetch data
        ticker = yf.Ticker(request.symbol)
        df = ticker.history(period=request.period, interval=request.interval)
        logger.debug(f"Retrieved {len(df)} candles for {request.symbol}")
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for symbol {request.symbol}")
            
        candles = []
        for index, row in df.iterrows():
            # yfinance index is datetime
            candles.append(PriceCandle(
                symbol=request.symbol,
                timestamp=index.to_pydatetime(),
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                volume=row['Volume']
            ))
            
        logger.info(f"Price history fetch complete for {request.symbol}. Returning {len(candles)} candles")
        return PriceHistoryResponse(symbol=request.symbol, candles=candles)
        
    except Exception as e:
        logger.error(f"Error fetching price history for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/price_history/test")
async def test_fetcher():
    """Test endpoint to verify yfinance connectivity"""
    try:
        ticker = yf.Ticker("AAPL")
        hist = ticker.history(period="1d")
        return {"status": "ok", "last_price": hist['Close'].iloc[-1]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
