from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from backend.models import NewsArticle
import random

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
    articles = []
    
    import yfinance as yf
    
    for symbol in request.symbols:
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
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
                if len(articles) >= request.limit:
                    break
                
                # Convert timestamp
                pub_time = datetime.fromtimestamp(item.get('providerPublishTime', 0))
                
                articles.append(NewsArticle(
                    title=item.get('title', 'No Title'),
                    url=item.get('link', ''),
                    source=item.get('publisher', 'Unknown'),
                    published_at=pub_time,
                    content=None, # yfinance doesn't provide full content
                    sentiment=None, 
                    related_symbols=[symbol]
                ))
                
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            continue
            
    return NewsFetchResponse(articles=articles)
