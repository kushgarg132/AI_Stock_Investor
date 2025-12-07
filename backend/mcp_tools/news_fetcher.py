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
    
    for symbol in symbols:
        try:
            logger.debug(f"Fetching news from yfinance for {symbol}")
            ticker = yf.Ticker(symbol)
            news = ticker.news
            logger.debug(f"Retrieved {len(news) if news else 0} news items for {symbol}")
            
            # yfinance news format:
            # {
            #   'uuid': '...',
            #   'title': '...',
            #   'publisher': '...',
            #   'link': '...',
            #   'providerPublishTime': 163...
            #   'type': 'STORY'
            # }
            
            for item in news:
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
                    related_symbols=[symbol]
                ))
                
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            continue
            
    logger.info(f"News fetch complete. Returning {len(articles)} articles")
    return articles
