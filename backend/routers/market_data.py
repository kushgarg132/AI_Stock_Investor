from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yfinance as yf
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# Indices to track
INDICES = {
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "INDIA VIX": "^INDIAVIX" # Might need verification, fallback to ^VIX if fails?
}

# Popular stocks for "Trending" (since we don't have a real trending API)
TRENDING_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ADANIENT.NS", "TATAMOTORS.NS"]

async def fetch_ticker_data(symbol: str, name: str) -> Dict[str, Any]:
    try:
        ticker = yf.Ticker(symbol)
        # Fast fetch using fast_info or history
        # fast_info is better for latest price
        price = ticker.fast_info.last_price
        prev_close = ticker.fast_info.previous_close
        
        if price is None or prev_close is None:
             # Fallback to history
             hist = ticker.history(period="2d")
             if len(hist) >= 1:
                 price = hist['Close'].iloc[-1]
                 prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else price
        
        if price is None:
            return None

        change = price - prev_close
        percent = (change / prev_close) * 100
        
        return {
            "name": name,
            "symbol": symbol,
            "value": price,
            "change": change,
            "percent": percent
        }
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

@router.get("/market/indices")
async def get_market_indices():
    tasks = [fetch_ticker_data(sym, name) for name, sym in INDICES.items()]
    results = await asyncio.gather(*tasks)
    # Filter out failed fetches
    return [r for r in results if r is not None]

@router.get("/market/trending")
async def get_trending_stocks():
    # Fetch real data for our "Trending" list
    # We can fetch names from yf.Ticker(sym).info but that's slow. 
    # Hardcoding names for speed for now or fetching minimally.
    
    # Map for display names
    NAMES = {
        "RELIANCE.NS": "Reliance Industries",
        "TCS.NS": "Tata Consultancy Svc",
        "HDFCBANK.NS": "HDFC Bank",
        "INFY.NS": "Infosys Ltd",
        "ADANIENT.NS": "Adani Enterprises",
        "TATAMOTORS.NS": "Tata Motors"
    }
    
    tasks = [fetch_ticker_data(sym, NAMES.get(sym, sym)) for sym in TRENDING_SYMBOLS]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
