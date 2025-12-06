from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import logging

import yfinance as yf
import pandas as pd
from backend.models import PriceCandle

# Try to import jugaad-data for Indian stocks
try:
    from jugaad_data.nse import stock_df
    JUGAAD_AVAILABLE = True
except ImportError:
    JUGAAD_AVAILABLE = False

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

def is_indian_stock(symbol: str) -> bool:
    """Check if symbol is an Indian stock (NSE/BSE)"""
    return symbol.endswith('.NS') or symbol.endswith('.BO')

def get_nse_symbol(symbol: str) -> str:
    """Extract NSE symbol from yfinance format"""
    # RELIANCE.NS -> RELIANCE
    if symbol.endswith('.NS'):
        return symbol[:-3]
    elif symbol.endswith('.BO'):
        return symbol[:-3]
    return symbol

def period_to_days(period: str) -> int:
    """Convert yfinance period to days"""
    mapping = {
        '1d': 1, '5d': 5, '1mo': 30, '3mo': 90,
        '6mo': 180, '1y': 365, '2y': 730, '5y': 1825,
        'ytd': 180, 'max': 3650
    }
    return mapping.get(period, 30)

def fetch_indian_stock_data(symbol: str, period: str) -> pd.DataFrame:
    """Fetch Indian stock data using jugaad-data"""
    nse_symbol = get_nse_symbol(symbol)
    days = period_to_days(period)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Fetching NSE data for {nse_symbol} from {start_date} to {end_date}")
    
    df = stock_df(symbol=nse_symbol, from_date=start_date, to_date=end_date, series="EQ")
    
    # Rename columns to match yfinance format
    df = df.rename(columns={
        'DATE': 'timestamp',
        'OPEN': 'Open',
        'HIGH': 'High',
        'LOW': 'Low',
        'CLOSE': 'Close',
        'VOLUME': 'Volume'
    })
    
    return df

@router.post("/price_history", response_model=PriceHistoryResponse)
async def fetch_price_history(request: PriceHistoryRequest):
    """
    Fetches historical price data for a given symbol.
    Uses yfinance first (faster), falls back to jugaad-data for Indian stocks if needed.
    """
    logger.info(f"Fetching price history for {request.symbol}, period: {request.period}, interval: {request.interval}")
    
    source = "yfinance"
    df = None
    
    try:
        # Try yfinance first (it's faster)
        ticker = yf.Ticker(request.symbol)
        df = ticker.history(period=request.period, interval=request.interval)
        
        # If yfinance returns empty for Indian stock, try jugaad-data as fallback
        if df.empty and is_indian_stock(request.symbol) and JUGAAD_AVAILABLE:
            logger.info(f"yfinance returned no data for {request.symbol}, trying jugaad-data...")
            try:
                df = fetch_indian_stock_data(request.symbol, request.period)
                source = "jugaad-data (NSE)"
            except Exception as e:
                logger.warning(f"jugaad-data also failed: {e}")
        
        logger.debug(f"Retrieved {len(df) if df is not None else 0} candles for {request.symbol}")
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for symbol {request.symbol}")

            
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
                symbol=request.symbol,
                timestamp=ts,
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=int(row.get('Volume', 0))
            ))
            
        logger.info(f"Price history fetch complete for {request.symbol} via {source}. Returning {len(candles)} candles")
        return PriceHistoryResponse(symbol=request.symbol, candles=candles, source=source)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price history for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    
    # Test jugaad-data
    if JUGAAD_AVAILABLE:
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=5)
            df = stock_df(symbol="RELIANCE", from_date=start_date, to_date=end_date, series="EQ")
            results["jugaad_data"] = {"status": "ok", "symbol": "RELIANCE", "rows": len(df)}
        except Exception as e:
            results["jugaad_data"] = {"status": "error", "detail": str(e)}
    else:
        results["jugaad_data"] = {"status": "not_installed"}
    
    return results

