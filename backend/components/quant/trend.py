from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import logging

import pandas as pd
from backend.components.shared.models import PriceCandle, Trend
from backend.components.quant.indicators import Indicators

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


logger = logging.getLogger(__name__)

class TrendDetector:
    @staticmethod
    def detect_trend(df: pd.DataFrame) -> Trend:
        """
        Detects the current trend based on SMA alignment and price action.
        """
        if len(df) < 200:
            return Trend.CHOPPY # Not enough data
            
        current_price = df['close'].iloc[-1]
        sma_50 = df['sma_50'].iloc[-1]
        sma_200 = df['sma_200'].iloc[-1]
        
        # Simple Golden Cross / Death Cross logic + Price location
        if current_price > sma_50 > sma_200:
            return Trend.UP
        elif current_price < sma_50 < sma_200:
            return Trend.DOWN
        else:
            return Trend.CHOPPY

    @staticmethod
    def analyze_market_structure(df: pd.DataFrame, window: int = 5) -> Trend:
        """
        Analyzes Higher Highs/Higher Lows for Uptrend, Lower Lows/Lower Highs for Downtrend.
        """
        # Simplified implementation looking at last few pivots
        # This would require the SupportResistance logic to find pivots first
        # For now, we rely on SMA alignment
        return TrendDetector.detect_trend(df)
