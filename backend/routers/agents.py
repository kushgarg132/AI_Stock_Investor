from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from backend.research.graph import ResearchAgent, ResearchReport

logger = logging.getLogger(__name__)

router = APIRouter()
research_agent = ResearchAgent()

class AnalyzeRequest(BaseModel):
    symbol: str
    account_size: float = 100000.0
    current_exposure: float = 0.0

@router.post("/analyze/{symbol}", response_model=ResearchReport)
async def analyze_stock(symbol: str, request: AnalyzeRequest = None):
    """
    Generate a research report (company info, news/sentiment, LLM thesis) for
    a given stock symbol. NOTE: this endpoint no longer produces a trade
    decision or signal -- see backend.scoring.composite / backend.strategies
    for that. account_size/current_exposure are accepted for request-body
    backward compatibility but are no longer used by the research pipeline.
    """
    logger.info(f"Received analyze request for {symbol}")

    try:
        result = await research_agent.run(symbol)
        logger.info(f"Research report complete for {symbol}")
        return result
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
