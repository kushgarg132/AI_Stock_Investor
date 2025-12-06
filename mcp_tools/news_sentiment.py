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
    logger.info(f"Analyzing sentiment for {len(request.articles)} articles")
    analyzed = []
    
    for article in request.articles:
        logger.debug(f"Processing article: {article.title[:50] if article.title else 'No Title'}...")
        # Construct prompt - handle None content
        content_preview = (article.content or "")[:200]
        prompt = f"""
        Analyze the following financial news headline and content:
        Title: {article.title}
        Content: {content_preview}...
        
        Determine:
        1. Sentiment (POSITIVE, NEGATIVE, NEUTRAL)
        2. Sentiment Score (-1.0 to 1.0)
        3. Impact Score (1-10, where 10 is market moving)
        
        Return JSON only: {{ "sentiment": "...", "score": 0.0, "impact": 0 }}
        """
        
        try:
            response = await llm_service.get_completion(
                prompt, 
                system_prompt="You are a financial sentiment analyst. Return strict JSON."
            )
            
            if response == "LLM_DISABLED":
                # Mock fallback
                article.sentiment = Sentiment.NEUTRAL
                article.sentiment_score = 0.0
                article.impact_score = 1
            else:
                # Clean response (remove markdown code blocks if present)
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                    
                data = json.loads(response.strip())
                # Handle potentially invalid sentiment values from LLM
                try:
                    article.sentiment = Sentiment(data["sentiment"].lower())
                except ValueError:
                    logger.warning(f"Unknown sentiment value '{data['sentiment']}', defaulting to NEUTRAL")
                    article.sentiment = Sentiment.NEUTRAL
                article.sentiment_score = float(data["score"])
                article.impact_score = int(data["impact"])
                logger.debug(f"Sentiment result: {article.sentiment}, score: {article.sentiment_score}")
                
        except Exception as e:
            # Fallback on error
            logger.error(f"Error analyzing sentiment: {e}")
            article.sentiment = Sentiment.NEUTRAL
            
        analyzed.append(article)
        
    logger.info(f"Sentiment analysis complete for {len(analyzed)} articles")
    return SentimentAnalysisResponse(analyzed_articles=analyzed)
