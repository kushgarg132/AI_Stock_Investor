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


# NIFTY 50 Symbols
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

NIFTY_50_SYMBOLS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS"
]

# Simple in-memory cache
class MarketCache:
    def __init__(self):
        self.data = None
        self.last_updated = 0
        self.ttl = 300  # 5 minutes

    def get(self):
        import time
        if self.data and (time.time() - self.last_updated < self.ttl):
            return self.data
        return None

    def set(self, data):
        import time
        self.data = data
        self.last_updated = time.time()

trending_cache = MarketCache()


@router.get("/market/indices")
async def get_market_indices():
    tasks = [fetch_ticker_data(sym, name) for name, sym in INDICES.items()]
    results = await asyncio.gather(*tasks)
    # Filter out failed fetches
    return [r for r in results if r is not None]

@router.get("/market/trending")
async def get_trending_stocks():
    # Check cache first
    cached_data = trending_cache.get()
    if cached_data:
        return cached_data

    # Fetch all NIFTY 50 stocks
    # The name is just the symbol for now to save complexity/time on additional fetches, 
    # or we could carry a map if specific names are needed.
    tasks = [fetch_ticker_data(sym, sym) for sym in NIFTY_50_SYMBOLS]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results and sort by absolute percentage change (volatility/trending)
    valid_results = [r for r in results if r is not None]
    
    # Sort by absolute percent change descending
    valid_results.sort(key=lambda x: abs(x['percent']), reverse=True)
    
    # Take top 6
    top_trending = valid_results[:6]
    
    # Update cache
    trending_cache.set(top_trending)
    
    return top_trending

# Global Indices
GLOBAL_INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225",
    "DAX": "^GDAXI",
}

@router.get("/market/global")
async def get_global_indices():
    """Fetch global market indices."""
    tasks = [fetch_ticker_data(sym, name) for name, sym in GLOBAL_INDICES.items()]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]

