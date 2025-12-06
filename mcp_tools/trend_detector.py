from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import pandas as pd
from backend.models import PriceCandle, Trend
from core.trend import TrendDetector
from core.indicators import Indicators

router = APIRouter()

class TrendRequest(BaseModel):
    candles: List[PriceCandle]

class TrendResponse(BaseModel):
    trend: Trend
    details: str

@router.post("/analysis/trend", response_model=TrendResponse)
async def detect_trend(request: TrendRequest):
    if not request.candles:
        return TrendResponse(trend=Trend.CHOPPY, details="No data")
        
    df = pd.DataFrame([c.model_dump() for c in request.candles])
    
    # Calculate indicators if needed (TrendDetector expects them)
    df = Indicators.calculate_all(df)
    
    trend = TrendDetector.detect_trend(df)
    
    return TrendResponse(trend=trend, details=f"Detected {trend.value} trend based on SMA alignment")
