from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import pandas as pd
from backend.models import PriceCandle

router = APIRouter()

class VolumeRequest(BaseModel):
    candles: List[PriceCandle]
    threshold_multiplier: float = 2.0

class VolumeResponse(BaseModel):
    is_spike: bool
    current_volume: float
    average_volume: float
    multiplier: float

@router.post("/analysis/volume_spike", response_model=VolumeResponse)
async def detect_volume_spike(request: VolumeRequest):
    if not request.candles:
        return VolumeResponse(is_spike=False, current_volume=0, average_volume=0, multiplier=0)
        
    df = pd.DataFrame([c.model_dump() for c in request.candles])
    
    if len(df) < 20:
        return VolumeResponse(is_spike=False, current_volume=df['volume'].iloc[-1], average_volume=0, multiplier=0)
        
    avg_vol = df['volume'].rolling(20).mean().iloc[-1]
    current_vol = df['volume'].iloc[-1]
    
    multiplier = current_vol / avg_vol if avg_vol > 0 else 0
    is_spike = multiplier >= request.threshold_multiplier
    
    return VolumeResponse(
        is_spike=is_spike,
        current_volume=current_vol,
        average_volume=avg_vol,
        multiplier=multiplier
    )
