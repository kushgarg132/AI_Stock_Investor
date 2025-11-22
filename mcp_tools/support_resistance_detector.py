from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import pandas as pd
from backend.models import PriceCandle
from core.support_resistance import SupportResistance

router = APIRouter()

class SRRequest(BaseModel):
    candles: List[PriceCandle]

class SRResponse(BaseModel):
    levels: List[float]
    nearest_support: float = None
    nearest_resistance: float = None

@router.post("/analysis/support_resistance", response_model=SRResponse)
async def detect_support_resistance(request: SRRequest):
    if not request.candles:
        return SRResponse(levels=[])
        
    df = pd.DataFrame([c.model_dump() for c in request.candles])
    levels = SupportResistance.identify_levels(df)
    
    current_price = df['close'].iloc[-1]
    sup, res = SupportResistance.get_nearest_levels(current_price, levels)
    
    return SRResponse(
        levels=levels,
        nearest_support=sup if sup else 0.0,
        nearest_resistance=res if res else 0.0
    )
