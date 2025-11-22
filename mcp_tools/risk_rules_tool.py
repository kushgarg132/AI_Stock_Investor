from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.risk import RiskRules

router = APIRouter()

class RiskCheckRequest(BaseModel):
    account_size: float
    risk_per_trade_percent: float = 1.0
    entry_price: float
    stop_loss: float
    symbol: str
    current_exposure: float = 0.0
    max_exposure: float = 100000.0

class RiskCheckResponse(BaseModel):
    approved: bool
    position_size_shares: float
    position_value: float
    reason: str

@router.post("/risk/check", response_model=RiskCheckResponse)
async def check_risk(request: RiskCheckRequest):
    """
    Evaluates a proposed trade against risk rules.
    """
    # 1. Calculate Position Size
    size = RiskRules.calculate_position_size(
        request.account_size,
        request.risk_per_trade_percent,
        request.entry_price,
        request.stop_loss
    )
    
    position_value = size * request.entry_price
    
    # 2. Check Exposure
    if not RiskRules.check_exposure_limit(request.current_exposure, request.max_exposure, position_value):
        return RiskCheckResponse(
            approved=False,
            position_size_shares=0,
            position_value=0,
            reason="Max exposure limit exceeded"
        )
        
    # 3. Sanity Checks
    if size <= 0:
        return RiskCheckResponse(
            approved=False,
            position_size_shares=0,
            position_value=0,
            reason="Invalid stop loss or calculation error"
        )
        
    return RiskCheckResponse(
        approved=True,
        position_size_shares=size,
        position_value=position_value,
        reason="Risk checks passed"
    )
