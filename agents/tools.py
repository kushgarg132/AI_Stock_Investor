from langchain_core.tools import tool
from typing import List
from mcp_tools.news_fetcher import fetch_news_logic
from mcp_tools.stock_info_fetcher import fetch_stock_info_logic
from mcp_tools.price_history_fetcher import fetch_price_history_logic
from backend.models import NewsArticle, CompanyInfo, PriceCandle

# --- Wrappers to ensuring typing compatibility if needed ---

@tool
async def fetch_news_tool(symbols: List[str], limit: int = 10) -> List[NewsArticle]:
    """
    Fetches latest news articles for the given stock symbols.
    
    Args:
        symbols: List of stock symbols (e.g., ["AAPL", "TSLA"])
        limit: Maximum number of articles to return (default: 10)
    """
    return await fetch_news_logic(symbols, limit)

@tool
async def fetch_stock_info_tool(symbol: str) -> CompanyInfo:
    """
    Fetches detailed company information and fundamentals for a given symbol.
    
    Args:
        symbol: The stock symbol (e.g., "AAPL")
    """
    return await fetch_stock_info_logic(symbol)

@tool
async def fetch_price_history_tool(symbol: str, period: str = "1mo", interval: str = "1d") -> List[PriceCandle]:
    """
    Fetches historical price candles for a given symbol.
    
    Args:
        symbol: The stock symbol
        period: Time period (e.g., "1d", "5d", "1mo", "6mo", "1y", "ytd", "max")
        interval: Data interval (e.g., "1m", "5m", "1h", "1d", "1wk")
    """
    candles, source = await fetch_price_history_logic(symbol, period, interval)
    return candles
