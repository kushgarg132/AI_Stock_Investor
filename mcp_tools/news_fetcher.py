from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from backend.models import NewsArticle, Sentiment
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
    Fetches news articles for the given symbols.
    Currently mocks data for demonstration purposes.
    """
    articles = []
    
    # Mock data generation
    # In a real implementation, this would call NewsAPI, AlphaVantage, etc.
    titles = [
        "Quarterly Earnings Beat Expectations",
        "CEO Announces New Product Line",
        "Market volatility increases amidst global tensions",
        "Analyst upgrades rating to Buy",
        "Supply chain issues persist for tech sector"
    ]
    
    sources = ["Bloomberg", "Reuters", "CNBC", "Financial Times"]
    
    for symbol in request.symbols:
        for _ in range(request.limit // len(request.symbols) + 1):
            if len(articles) >= request.limit:
                break
                
            title = f"{symbol}: {random.choice(titles)}"
            articles.append(NewsArticle(
                title=title,
                url=f"https://example.com/news/{random.randint(1000,9999)}",
                source=random.choice(sources),
                published_at=datetime.now(),
                content=f"Sample content for {title}...",
                sentiment=None, # To be filled by sentiment analysis tool
                related_symbols=[symbol]
            ))
            
    return NewsFetchResponse(articles=articles)
