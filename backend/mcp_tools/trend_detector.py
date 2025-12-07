from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import logging

import pandas as pd
from backend.models import PriceCandle, Trend
from backend.core.trend import TrendDetector
from backend.core.indicators import Indicators

logger = logging.getLogger(__name__)

router = APIRouter()

class TrendRequest(BaseModel):
    candles: List[PriceCandle]

class TrendResponse(BaseModel):
    trend: Trend
    details: str

@router.post("/analysis/trend", response_model=TrendResponse)
async def detect_trend(request: TrendRequest):
    """
    Detects trend based on candles.
    """
    trend, details = detect_trend_logic(request.candles)
    return TrendResponse(trend=trend, details=details)

def detect_trend_logic(candles: List[PriceCandle]) -> tuple[Trend, str]:
    logger.info(f"Detecting trend for {len(candles)} candles")
    if not candles:
        logger.warning("No candles provided for trend detection")
        return Trend.CHOPPY, "No data"
        
    df = pd.DataFrame([c.model_dump() for c in candles])
    
    # Calculate indicators if needed (TrendDetector expects them)
    df = Indicators.calculate_all(df)
    
    trend = TrendDetector.detect_trend(df)
    
    logger.info(f"Trend detection complete: {trend.value}")
    return trend, f"Detected {trend.value} trend based on SMA alignment"
