from fastapi import APIRouter, HTTPException, BackgroundTasks
from backend.models import Watchlist
from backend.database import db
from datetime import datetime
from typing import List, Dict, Any
from backend.mcp_tools.stock_info_fetcher import fetch_stock_info_logic

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

@router.get("/{user_id}", response_model=Watchlist)
async def get_watchlist(user_id: str):
    """Get a user's watchlist. Creates one if it doesn't exist."""
    collection = db.db.watchlist
    
    watchlist = await collection.find_one({"user_id": user_id})
    
    if not watchlist:
        # Create empty watchlist
        new_watchlist = Watchlist(user_id=user_id, symbols=[])
        await collection.insert_one(new_watchlist.model_dump())
        return new_watchlist
        
    return Watchlist(**watchlist)

@router.post("/{user_id}/add", response_model=Watchlist)
async def add_to_watchlist(user_id: str, symbol: str):
    """Add a symbol to the user's watchlist."""
    symbol = symbol.upper()
    collection = db.db.watchlist
    
    # Ensure exists
    watchlist = await get_watchlist(user_id)
    
    if symbol not in watchlist.symbols:
        await collection.update_one(
            {"user_id": user_id},
            {
                "$push": {"symbols": symbol},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        watchlist.symbols.append(symbol)
        
    return watchlist

@router.delete("/{user_id}/remove/{symbol}", response_model=Watchlist)
async def remove_from_watchlist(user_id: str, symbol: str):
    """Remove a symbol from the user's watchlist."""
    symbol = symbol.upper()
    collection = db.db.watchlist
    
    await collection.update_one(
        {"user_id": user_id},
        {
            "$pull": {"symbols": symbol},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    return await get_watchlist(user_id)

@router.get("/{user_id}/details", response_model=List[Dict[str, Any]])
async def get_watchlist_details(user_id: str):
    """Get detailed stock info for all symbols in the watchlist."""
    watchlist = await get_watchlist(user_id)
    details = []
    
    # Ideally use concurrent fetching, keeping simple for now
    for sym in watchlist.symbols:
        try:
            info = await fetch_stock_info_logic(sym)
            details.append(info.model_dump())
        except Exception:
            # Fallback for error
            details.append({"symbol": sym, "error": "Failed to fetch data"})
            
    return details
