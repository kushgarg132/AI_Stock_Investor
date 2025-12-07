from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from backend.core.risk import RiskRules

logger = logging.getLogger(__name__)

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
    return check_risk_logic(
        account_size=request.account_size,
        risk_per_trade_percent=request.risk_per_trade_percent,
        entry_price=request.entry_price,
        stop_loss=request.stop_loss,
        symbol=request.symbol,
        current_exposure=request.current_exposure,
        max_exposure=request.max_exposure
    )

def check_risk_logic(account_size: float, risk_per_trade_percent: float, entry_price: float, stop_loss: float, symbol: str, current_exposure: float, max_exposure: float = 100000.0) -> RiskCheckResponse:
    logger.info(f"Checking risk for {symbol}: entry={entry_price}, stop={stop_loss}, account={account_size}")
    # 1. Calculate Position Size
    size = RiskRules.calculate_position_size(
        account_size,
        risk_per_trade_percent,
        entry_price,
        stop_loss
    )
    
    position_value = size * entry_price
    
    # 2. Check Exposure
    if not RiskRules.check_exposure_limit(current_exposure, max_exposure, position_value):
        logger.warning(f"Risk check REJECTED for {symbol}: Max exposure limit exceeded")
        return RiskCheckResponse(
            approved=False,
            position_size_shares=0,
            position_value=0,
            reason="Max exposure limit exceeded"
        )
        
    # 3. Sanity Checks
    if size <= 0:
        logger.warning(f"Risk check REJECTED for {symbol}: Invalid stop loss or calculation error")
        return RiskCheckResponse(
            approved=False,
            position_size_shares=0,
            position_value=0,
            reason="Invalid stop loss or calculation error"
        )
        
    logger.info(f"Risk check APPROVED for {symbol}: {size:.4f} shares, value=${position_value:.2f}")
    return RiskCheckResponse(
        approved=True,
        position_size_shares=size,
        position_value=position_value,
        reason="Risk checks passed"
    )
