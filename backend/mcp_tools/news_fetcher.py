from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
import logging

from backend.models import NewsArticle
import random

logger = logging.getLogger(__name__)

router = APIRouter()

class NewsFetchRequest(BaseModel):
    symbols: List[str]
    limit: int = 10

class NewsFetchResponse(BaseModel):
    articles: List[NewsArticle]

@router.post("/news/fetch", response_model=NewsFetchResponse)
async def fetch_news(request: NewsFetchRequest):
    """
    Fetches news articles for the given symbols using yfinance.
    """
    articles = await fetch_news_logic(request.symbols, request.limit)
    return NewsFetchResponse(articles=articles)

async def fetch_news_logic(symbols: List[str], limit: int = 10) -> List[NewsArticle]:
    """
    Core logic to fetch news from yfinance.
    """
    logger.info(f"Fetching news for symbols: {symbols}, limit: {limit}")
    articles = []
    
    import yfinance as yf
    
    suffixes = ["", ".NS", ".BO"]

    for symbol in symbols:
        found_news = []
        used_symbol = symbol
        
        # Try suffixes until we find news
        for suffix in suffixes:
            try_symbol = f"{symbol}{suffix}"
            try:
                logger.debug(f"Fetching news from yfinance for {try_symbol}")
                ticker = yf.Ticker(try_symbol)
                fetched = ticker.news
                if fetched:
                    found_news = fetched
                    used_symbol = try_symbol
                    logger.debug(f"Retrieved {len(fetched)} news items for {try_symbol}")
                    break
            except Exception as e:
                logger.debug(f"Failed to fetch news for {try_symbol}: {e}")
                continue
        
        if not found_news:
            logger.warning(f"No news found for {symbol} (tried suffixes: {suffixes})")
            continue
            
        # Process found news
        try:
            for item in found_news:
                if len(articles) >= limit:
                    break
                
                # Handle new yfinance structure (nested in 'content')
                if 'content' in item and isinstance(item['content'], dict):
                    content = item['content']
                    title = content.get('title', 'No Title')
                    url = content.get('clickThroughUrl', {}).get('url', '')
                    publisher = content.get('provider', {}).get('displayName', 'Unknown')
                    pub_date_str = content.get('pubDate')
                    try:
                        # Format: 2025-12-06T11:00:17Z
                        pub_time = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%SZ")
                    except Exception:
                        pub_time = datetime.now()
                else:
                    # Fallback to old structure
                    title = item.get('title', 'No Title')
                    url = item.get('link', '')
                    publisher = item.get('publisher', 'Unknown')
                    try:
                        pub_time = datetime.fromtimestamp(item.get('providerPublishTime', 0))
                    except:
                        pub_time = datetime.now()
                
                articles.append(NewsArticle(
                    title=title,
                    url=url,
                    source=publisher,
                    published_at=pub_time,
                    content=None, 
                    sentiment=None, 
                    related_symbols=[used_symbol]
                ))
                
        except Exception as e:
            logger.error(f"Error processing news for {used_symbol}: {e}")
            continue
            
    logger.info(f"News fetch complete. Returning {len(articles)} articles")
    return articles
