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
    company_info = await fetch_stock_info_logic(request.symbol)
    return StockInfoResponse(company_info=company_info)

async def fetch_stock_info_logic(symbol: str) -> CompanyInfo:
    """
    Core logic to fetch stock info from yfinance.
    """
    logger.info(f"Fetching stock info for {symbol}")
    import yfinance as yf
    
    # Try multiple suffixes: original, NSE, BSE
    suffixes = ["", ".NS", ".BO"]
    last_exception = None
    
    for suffix in suffixes:
        try_symbol = f"{symbol}{suffix}"
        logger.info(f"Attempting to fetch info for {try_symbol}")
        
        try:
            ticker = yf.Ticker(try_symbol)
            # Need to force a check, .info usually does network call
            info = ticker.info
            
            # Check if valid data came back
            # yfinance often returns empty info or {'regularMarketPrice': None} for invalid symbols
            # Check if valid data came back
            # yfinance often returns empty info or {'regularMarketPrice': None} for invalid symbols
            current_price_val = info.get('regularMarketPrice') or info.get('currentPrice')
            
            if not info or current_price_val is None:
                 # Try history as fallback check
                 # data might be missing, but let's see if we can get price from history
                hist = ticker.history(period="5d")
                if hist.empty:
                    # This attempt failed, continue to next suffix
                    logger.info(f"No price data or history for {try_symbol}, trying next...")
                    continue
                
                # If history exists, we have a match
                current_price = float(hist['Close'].iloc[-1])
                previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                day_change = current_price - previous_close
                day_change_percent = (day_change / previous_close) * 100 if previous_close else 0
                
                company_info = CompanyInfo(
                    symbol=try_symbol.upper(),
                    name=try_symbol.upper(),
                    current_price=current_price,
                    previous_close=previous_close,
                    day_change=day_change,
                    day_change_percent=day_change_percent,
                    volume=float(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else None,
                    currency="INR" if suffix in ['.NS', '.BO'] else "USD" # Fallback guess if info is empty
                )
                logger.info(f"Stock info fetch complete for {try_symbol} (via history)")
                return company_info

            # Full info available
            current_price = info.get('regularMarketPrice') or info.get('currentPrice', 0)
            previous_close = info.get('previousClose', current_price)
            day_change = current_price - previous_close if previous_close else 0
            day_change_percent = (day_change / previous_close) * 100 if previous_close else 0
            
            company_info = CompanyInfo(
                symbol=try_symbol.upper(),
                name=info.get('longName') or info.get('shortName', try_symbol.upper()),
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
                beta=info.get('beta'),
                currency=info.get('currency', 'USD'),
                logo_url=info.get('logo_url') or (
                    f"https://logo.clearbit.com/{info['website'].replace('https://', '').replace('http://', '').replace('www.', '').strip('/').split('/')[0]}" 
                    if info.get('website') else 
                    f"https://logo.clearbit.com/{symbol.lower()}.com" # Last resort fallback
                ),
                
                # Extended Fundamentals
                peg_ratio=info.get('pegRatio'),
                price_to_book=info.get('priceToBook'),
                trailing_eps=info.get('trailingEps'),
                forward_eps=info.get('forwardEps'),
                return_on_equity=info.get('returnOnEquity'),
                return_on_assets=info.get('returnOnAssets'),
                revenue_growth=info.get('revenueGrowth'),
                total_revenue=info.get('totalRevenue'),
                total_debt=info.get('totalDebt'),
                total_cash=info.get('totalCash'),
                ebitda=info.get('ebitda'),
                operating_margins=info.get('operatingMargins'),
                gross_margins=info.get('grossMargins')

            )
            
            logger.info(f"Stock info fetch complete for {try_symbol}: {company_info.name}")
            return company_info
            
        except Exception as e:
            logger.info(f"Error fetching {try_symbol}: {e}")
            last_exception = e
            continue

    # If all fail
    logger.error(f"Failed to fetch stock info for {symbol} after trying suffixes {suffixes}")
    raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol} (tried suffixes: {suffixes})")


@router.get("/stock_info/{symbol}", response_model=StockInfoResponse)
async def fetch_stock_info_get(symbol: str):
    """GET endpoint for fetching stock info."""
    return await fetch_stock_info(StockInfoRequest(symbol=symbol))
