from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import logging
import json

from backend.models import NewsArticle, Sentiment
from backend.llm import llm_service

logger = logging.getLogger(__name__)

router = APIRouter()

class SentimentAnalysisRequest(BaseModel):
    articles: List[NewsArticle]

class SentimentAnalysisResponse(BaseModel):
    analyzed_articles: List[NewsArticle]

@router.post("/news/sentiment", response_model=SentimentAnalysisResponse)
async def analyze_sentiment(request: SentimentAnalysisRequest):
    """
    Analyzes the sentiment of the provided news articles using an LLM.
    Updates the sentiment, sentiment_score, and impact_score fields.
    """
    analyzed = await analyze_sentiment_logic(request.articles)
    return SentimentAnalysisResponse(analyzed_articles=analyzed)

async def analyze_sentiment_logic(articles: List[NewsArticle], target_symbol: str = None) -> List[NewsArticle]:
    logger.info(f"Analyzing sentiment for {len(articles)} articles (Target: {target_symbol})")
    analyzed = []
    
    for article in articles:
        logger.debug(f"Processing article: {article.title[:50] if article.title else 'No Title'}...")
        
        # Construct prompt - handle None content
        content_preview = (article.content or "")[:500] # Increased context
        
        prompt = f"""
        You are a senior financial analyst. Analyze the following news for the stock symbol: {target_symbol if target_symbol else "GENERAL MARKET"}.
        
        News Headline: {article.title}
        News Content: {content_preview}
        
        Step 1: Relevance Check
        - Is this article directly relevant to {target_symbol if target_symbol else "finance"}? 
        - If it mentions {target_symbol} only in passing (e.g., as part of a list of top gainers) with no specific news, relevance is LOW.
        - If it discusses earnings, products, management, or sector trends affecting {target_symbol}, relevance is HIGH.
        
        Step 2: Sentiment Analysis
        - Determine the sentiment (POSITIVE, NEGATIVE, NEUTRAL).
        - Assign a score (-1.0 to 1.0).
        - Assign an impact score (1-10). 10 = massive market mover (e.g. merger, earnings beat). 1 = noise.
        
        Step 3: Reasoning
        - Explain in one sentence WHY you assigned this score.
        
        Return strict JSON format:
        {{
            "is_relevant": true,
            "relevance_reason": "...",
            "sentiment": "POSITIVE",
            "score": 0.5,
            "impact": 5,
            "reasoning": "..."
        }}
        
        If NOT relevant, return: {{ "is_relevant": false, "relevance_reason": "Not about target stock" }}
        """
        
        try:
            response = await llm_service.get_completion(
                prompt, 
                system_prompt="You are a simplified financial reasoning engine. Return strict JSON only."
            )
            
            if response == "LLM_DISABLED":
                # Mock fallback
                article.sentiment = Sentiment.NEUTRAL
                article.sentiment_score = 0.0
                article.impact_score = 1
            else:
                # Clean response
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                    
                data = json.loads(response.strip())
                
                # Check relevance first
                if not data.get("is_relevant", True) and target_symbol:
                    logger.info(f"Article skipped due to low relevance: {article.title[:30]}...")
                    article.sentiment = Sentiment.NEUTRAL
                    article.sentiment_score = 0.0
                    article.impact_score = 0
                    # We could strictly remove it, but keeping it as NEUTRAL/0 impact is safer for now
                else:
                    try:
                        article.sentiment = Sentiment(data.get("sentiment", "neutral").lower())
                    except ValueError:
                        article.sentiment = Sentiment.NEUTRAL
                    
                    article.sentiment_score = float(data.get("score", 0.0))
                    article.impact_score = int(data.get("impact", 0))
                    # Store reasoning? Models don't have reasoning field yet.
                    # We could append it to content or summary later. For now, it just improves the score quality.
                    
                logger.debug(f"Sentiment result: {article.sentiment}, score: {article.sentiment_score}")
                
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            article.sentiment = Sentiment.NEUTRAL
            
        analyzed.append(article)
        
    logger.info(f"Sentiment analysis complete for {len(analyzed)} articles")
    return analyzed
