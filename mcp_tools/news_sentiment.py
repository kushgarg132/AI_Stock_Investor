from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from backend.models import NewsArticle, Sentiment
from backend.llm import llm_service
import json

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
    analyzed = []
    
    for article in request.articles:
        if not article:
            continue
            
        try:
            # Construct prompt
            content = article.content if article.content else ""
            prompt = f"""
            Analyze the following financial news headline and content:
            Title: {article.title}
            Content: {content[:200]}...
            
            Determine:
            1. Sentiment (POSITIVE, NEGATIVE, NEUTRAL)
            2. Sentiment Score (-1.0 to 1.0)
            3. Impact Score (1-10, where 10 is market moving)
            
            Return JSON only: {{ "sentiment": "...", "score": 0.0, "impact": 0 }}
            """
            
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
                article.sentiment = Sentiment(data["sentiment"].lower())
                article.sentiment_score = float(data["score"])
                article.impact_score = int(data["impact"])
                    
        except Exception as e:
            # Fallback on error
            print(f"Error analyzing sentiment for article {article.title[:20] if article and article.title else 'Unknown'}: {e}")
            article.sentiment = Sentiment.NEUTRAL
            
        analyzed.append(article)
        
    return SentimentAnalysisResponse(analyzed_articles=analyzed)
