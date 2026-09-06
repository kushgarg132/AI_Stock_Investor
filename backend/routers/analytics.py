"""/analytics/* -- the numbers behind the dashboard's P&L cards."""

from fastapi import APIRouter, Depends

from backend.analytics import compute_pnl
from backend.auth.dependency import get_current_user
from backend.auth.models import User
from backend.database import db
from backend.engine.persistence import LedgerStore
from backend.ws.publish import publisher_for
from backend.marks import mark_prices

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_ledger_store(user: User = Depends(get_current_user)) -> LedgerStore:
    return LedgerStore(db.db, user_id=user.id, on_change=publisher_for(user.id))


@router.get("/pnl")
async def get_pnl(ledger: LedgerStore = Depends(get_ledger_store)):
    positions = await ledger.get_open_positions()
    marks = await mark_prices(db.db, positions.keys())
    return await compute_pnl(ledger, marks)
