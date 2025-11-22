import httpx
from typing import List, Dict, Any
from pydantic import BaseModel
from backend.models import NewsArticle, FinancialEvent
from backend.llm import llm_service
from configs.settings import settings

class AnalystOutput(BaseModel):
    symbol: str
    sentiment_score: float
    impact_score: int
    summary: str
    events: List[FinancialEvent]

class AnalystAgent:
    def __init__(self):
        self.base_url = f"http://localhost:8000{settings.API_PREFIX}"
        
    async def analyze(self, symbol: str) -> AnalystOutput:
        """
        Orchestrates the news analysis workflow:
        1. Fetch News
        2. Analyze Sentiment
        3. Detect Events
        4. Synthesize Summary
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Fetch News
            try:
                news_response = await client.post(
                    f"{self.base_url}/news/fetch",
                    json={"symbols": [symbol], "limit": 5}
                )
                news_response.raise_for_status()
                articles = news_response.json()["articles"]
            except Exception as e:
                print(f"AnalystAgent Error fetching news: {e}")
                return self._empty_output(symbol)

            if not articles:
                return self._empty_output(symbol)

            # 2. Analyze Sentiment
            try:
                sentiment_response = await client.post(
                    f"{self.base_url}/news/sentiment",
                    json={"articles": articles}
                )
                sentiment_response.raise_for_status()
                analyzed_articles = sentiment_response.json()["analyzed_articles"]
            except Exception as e:
                 print(f"AnalystAgent Error analyzing sentiment: {e}")
                 analyzed_articles = articles # Fallback to raw articles

            # 3. Detect Events (from concatenated text or titles)
            combined_text = "\n".join([f"{a['title']}: {a.get('content', '')[:100]}" for a in analyzed_articles])
            events = []
            try:
                event_response = await client.post(
                    f"{self.base_url}/events/classify",
                    json={"text": combined_text}
                )
                event_response.raise_for_status()
                events = event_response.json()["events"]
            except Exception as e:
                print(f"AnalystAgent Error classifying events: {e}")

            # 4. Synthesize Summary using LLM
            summary_prompt = f"""
            Synthesize a brief market sentiment summary for {symbol} based on these news articles:
            {combined_text[:2000]}
            
            Events detected: {events}
            
            Return a concise paragraph.
            """
            summary = await llm_service.get_completion(summary_prompt, system_prompt="You are a financial analyst.")
            
            # Calculate aggregate scores
            avg_sentiment = sum(a.get('sentiment_score', 0) for a in analyzed_articles) / len(analyzed_articles) if analyzed_articles else 0
            max_impact = max([a.get('impact_score', 0) for a in analyzed_articles] + [0])
            
            return AnalystOutput(
                symbol=symbol,
                sentiment_score=avg_sentiment,
                impact_score=max_impact,
                summary=summary,
                events=[FinancialEvent(**e) for e in events]
            )

    def _empty_output(self, symbol: str) -> AnalystOutput:
        return AnalystOutput(
            symbol=symbol,
            sentiment_score=0.0,
            impact_score=0,
            summary="No news found or error in analysis.",
            events=[]
        )
