from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import logging

import pandas as pd
from backend.models import PriceCandle
from backend.core.support_resistance import SupportResistance

logger = logging.getLogger(__name__)

router = APIRouter()

class SRRequest(BaseModel):
    candles: List[PriceCandle]

class SRResponse(BaseModel):
    levels: List[float]
    nearest_support: float = None
    nearest_resistance: float = None

@router.post("/analysis/support_resistance", response_model=SRResponse)
async def detect_support_resistance(request: SRRequest):
    """
    Detects support/resistance levels.
    """
    return detect_support_resistance_logic(request.candles)

def detect_support_resistance_logic(candles: List[PriceCandle]) -> SRResponse:
    logger.info(f"Detecting support/resistance levels for {len(candles)} candles")
    if not candles:
        logger.warning("No candles provided for S/R detection")
        return SRResponse(levels=[])
        
    df = pd.DataFrame([c.model_dump() for c in candles])
    levels = SupportResistance.identify_levels(df)
    
    current_price = df['close'].iloc[-1]
    sup, res = SupportResistance.get_nearest_levels(current_price, levels)
    
    logger.info(f"S/R detection complete. Found {len(levels)} levels. Support: {sup}, Resistance: {res}")
    return SRResponse(
        levels=levels,
        nearest_support=sup if sup else 0.0,
        nearest_resistance=res if res else 0.0
    )
