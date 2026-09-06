from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from backend.components.shared.models import CompanyInfo
from backend.data.providers.yfinance_provider import YFinanceProvider
from backend.database import get_database
from backend.instruments.master import InstrumentMaster
from backend.instruments.resolve import SymbolNotFoundError, resolve_symbol

logger = logging.getLogger(__name__)

router = APIRouter()

_provider = YFinanceProvider()


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
    Core logic to fetch stock info: resolve `symbol` to an exact instrument,
    then fetch via YFinanceProvider. No suffix guessing.
    """
    logger.info(f"Fetching stock info for {symbol}")

    master = InstrumentMaster(await get_database())
    try:
        instrument = await resolve_symbol(symbol, master)
    except SymbolNotFoundError as e:
        logger.error(f"Failed to resolve symbol {symbol}: {e}")
        raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}: {e}")

    try:
        info = await _provider.info(instrument)
    except ValueError as e:
        logger.error(f"Failed to fetch stock info for {symbol} ({instrument.tradingsymbol}): {e}")
        raise HTTPException(status_code=404, detail=str(e))

    ticker_symbol = info["_ticker_symbol"]
    currency = "INR" if instrument.exchange in ("NSE", "BSE") else "USD"

    if info.get("_from_history_fallback"):
        current_price = info["regularMarketPrice"]
        previous_close = info["previousClose"]
        day_change = current_price - previous_close
        day_change_percent = (day_change / previous_close) * 100 if previous_close else 0

        company_info = CompanyInfo(
            symbol=instrument.tradingsymbol.upper(),
            name=instrument.name,
            current_price=current_price,
            previous_close=previous_close,
            day_change=day_change,
            day_change_percent=day_change_percent,
            volume=info.get("regularMarketVolume"),
            currency=currency,
        )
        logger.info(f"Stock info fetch complete for {ticker_symbol} (via history)")
        return company_info

    current_price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
    previous_close = info.get("previousClose", current_price)
    day_change = current_price - previous_close if previous_close else 0
    day_change_percent = (day_change / previous_close) * 100 if previous_close else 0

    company_info = CompanyInfo(
        symbol=instrument.tradingsymbol.upper(),
        name=info.get("longName") or info.get("shortName") or instrument.name,
        sector=info.get("sector"),
        industry=info.get("industry"),
        market_cap=info.get("marketCap"),
        current_price=current_price,
        previous_close=previous_close,
        day_change=day_change,
        day_change_percent=day_change_percent,
        week_52_high=info.get("fiftyTwoWeekHigh"),
        week_52_low=info.get("fiftyTwoWeekLow"),
        volume=info.get("regularMarketVolume") or info.get("volume"),
        avg_volume=info.get("averageVolume"),
        pe_ratio=info.get("trailingPE") or info.get("forwardPE"),
        dividend_yield=info.get("dividendYield"),
        beta=info.get("beta"),
        currency=info.get("currency", currency),
        logo_url=info.get("logo_url") or (
            f"https://logo.clearbit.com/{info['website'].replace('https://', '').replace('http://', '').replace('www.', '').strip('/').split('/')[0]}"
            if info.get("website") else
            f"https://logo.clearbit.com/{instrument.tradingsymbol.lower()}.com"  # Last resort fallback
        ),

        # Extended Fundamentals
        peg_ratio=info.get("pegRatio"),
        price_to_book=info.get("priceToBook"),
        trailing_eps=info.get("trailingEps"),
        forward_eps=info.get("forwardEps"),
        return_on_equity=info.get("returnOnEquity"),
        return_on_assets=info.get("returnOnAssets"),
        revenue_growth=info.get("revenueGrowth"),
        total_revenue=info.get("totalRevenue"),
        total_debt=info.get("totalDebt"),
        total_cash=info.get("totalCash"),
        ebitda=info.get("ebitda"),
        operating_margins=info.get("operatingMargins"),
        gross_margins=info.get("grossMargins"),
    )

    logger.info(f"Stock info fetch complete for {ticker_symbol}: {company_info.name}")
    return company_info


@router.get("/stock_info/{symbol}", response_model=StockInfoResponse)
async def fetch_stock_info_get(symbol: str):
    """GET endpoint for fetching stock info."""
    return await fetch_stock_info(StockInfoRequest(symbol=symbol))
