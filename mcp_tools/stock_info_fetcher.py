from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

import yfinance as yf
from backend.models import CompanyInfo

logger = logging.getLogger(__name__)

router = APIRouter()


class StockInfoRequest(BaseModel):
    symbol: str


class StockInfoResponse(BaseModel):
    company_info: CompanyInfo


@router.post("/stock_info", response_model=StockInfoResponse)
async def fetch_stock_info(request: StockInfoRequest):
    """
    Fetches comprehensive stock/company information using yfinance.
    """
    logger.info(f"Fetching stock info for {request.symbol}")
    try:
        ticker = yf.Ticker(request.symbol)
        info = ticker.info
        
        if not info or 'regularMarketPrice' not in info:
            # Try to get basic info from history
            hist = ticker.history(period="5d")
            if hist.empty:
                raise HTTPException(status_code=404, detail=f"No data found for symbol {request.symbol}")
            
            current_price = float(hist['Close'].iloc[-1])
            previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            day_change = current_price - previous_close
            day_change_percent = (day_change / previous_close) * 100 if previous_close else 0
            
            company_info = CompanyInfo(
                symbol=request.symbol.upper(),
                name=request.symbol.upper(),
                current_price=current_price,
                previous_close=previous_close,
                day_change=day_change,
                day_change_percent=day_change_percent,
                volume=float(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else None
            )
        else:
            # Full info available
            current_price = info.get('regularMarketPrice') or info.get('currentPrice', 0)
            previous_close = info.get('previousClose', current_price)
            day_change = current_price - previous_close if previous_close else 0
            day_change_percent = (day_change / previous_close) * 100 if previous_close else 0
            
            company_info = CompanyInfo(
                symbol=request.symbol.upper(),
                name=info.get('longName') or info.get('shortName', request.symbol.upper()),
                sector=info.get('sector'),
                industry=info.get('industry'),
                market_cap=info.get('marketCap'),
                current_price=current_price,
                previous_close=previous_close,
                day_change=day_change,
                day_change_percent=day_change_percent,
                week_52_high=info.get('fiftyTwoWeekHigh'),
                week_52_low=info.get('fiftyTwoWeekLow'),
                volume=info.get('regularMarketVolume') or info.get('volume'),
                avg_volume=info.get('averageVolume'),
                pe_ratio=info.get('trailingPE') or info.get('forwardPE'),
                dividend_yield=info.get('dividendYield'),
                beta=info.get('beta')
            )
        
        logger.info(f"Stock info fetch complete for {request.symbol}: {company_info.name}")
        return StockInfoResponse(company_info=company_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stock info for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock_info/{symbol}", response_model=StockInfoResponse)
async def fetch_stock_info_get(symbol: str):
    """GET endpoint for fetching stock info."""
    return await fetch_stock_info(StockInfoRequest(symbol=symbol))
