import httpx
from typing import Optional
from pydantic import BaseModel
from backend.models import TradeSignal
from configs.settings import settings

class RiskOutput(BaseModel):
    approved: bool
    adjusted_signal: Optional[TradeSignal]
    reason: str

class RiskAgent:
    def __init__(self):
        self.base_url = f"http://localhost:8000{settings.API_PREFIX}"
        
    async def evaluate(self, signal: TradeSignal, account_size: float, current_exposure: float) -> RiskOutput:
        """
        Evaluates a trade signal and calculates position size.
        """
        if not signal.entry_price or not signal.stop_loss:
            return RiskOutput(approved=False, adjusted_signal=None, reason="Missing entry or stop loss")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/risk/check",
                    json={
                        "account_size": account_size,
                        "risk_per_trade_percent": 1.0, # Configurable
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "symbol": signal.symbol,
                        "current_exposure": current_exposure
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                if result["approved"]:
                    # Update signal with calculated size
                    signal.position_size = result["position_size_shares"]
                    return RiskOutput(approved=True, adjusted_signal=signal, reason=result["reason"])
                else:
                    return RiskOutput(approved=False, adjusted_signal=None, reason=result["reason"])
                    
            except Exception as e:
                print(f"RiskAgent Error: {e}")
                return RiskOutput(approved=False, adjusted_signal=None, reason=f"Error checking risk: {e}")
