from fastapi import APIRouter, HTTPException
from agents.master_agent import MasterAgent, MasterOutput
from pydantic import BaseModel

router = APIRouter()
master_agent = MasterAgent()

class AnalyzeRequest(BaseModel):
    symbol: str
    account_size: float = 100000.0
    current_exposure: float = 0.0

@router.post("/analyze/{symbol}", response_model=MasterOutput)
async def analyze_stock(symbol: str, request: AnalyzeRequest = None):
    """
    Trigger the full multi-agent analysis pipeline for a given stock symbol.
    """
    # Handle optional body
    account_size = 100000.0
    current_exposure = 0.0
    
    if request:
        account_size = request.account_size
        current_exposure = request.current_exposure
        
    try:
        result = await master_agent.run(symbol, account_size, current_exposure)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
