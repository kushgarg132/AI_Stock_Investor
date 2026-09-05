"""/trading/* -- paper-trading control plane and read-only ledger queries.

`start_background_run`/`stop_background_run` are deliberately factored out
of the HTTP handlers: they own nothing but the asyncio.Task bookkeeping, so
they can be unit-tested directly against a fake feed that would otherwise
run forever, without needing a real Mongo/yfinance round-trip (see
backend/tests/test_trading_router.py).
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.components.quant.indian_stocks import ALL_SCAN_STOCKS
from backend.core.clock import SystemClock
from backend.database import db
from backend.data.providers.yfinance_provider import YFinanceProvider
from backend.data.feeds.polling_live import PollingLiveFeed
from backend.engine.execution.simulated import SimulatedExecutionClient
from backend.engine.persistence import LedgerStore
from backend.engine.portfolio import Portfolio
from backend.engine.runner import run
from backend.instruments.master import InstrumentMaster
from backend.strategies.registry import build_default_strategies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trading", tags=["Trading"])

# run_id -> the background asyncio.Task driving that run's engine loop.
_RUNS: dict[str, asyncio.Task] = {}

_MODE_TIMEFRAME = {"INTRADAY": "5m", "LONGTERM": "1d"}


def get_ledger_store() -> LedgerStore:
    return LedgerStore(db.db)


# ---------------------------------------------------------------------------
# Background-task plumbing (testable independent of FastAPI/Mongo/yfinance)
# ---------------------------------------------------------------------------

def start_background_run(coro) -> str:
    """Schedules `coro` as a background asyncio.Task and returns a run_id
    that /trading/stop (or stop_background_run directly) can cancel by.
    Never awaits the coroutine itself -- the whole point is the HTTP
    request returns immediately even though the engine loop runs
    indefinitely against a live feed."""
    run_id = str(uuid.uuid4())
    task = asyncio.create_task(coro)
    _RUNS[run_id] = task

    def _cleanup(_task: asyncio.Task) -> None:
        _RUNS.pop(run_id, None)

    task.add_done_callback(_cleanup)
    return run_id


async def stop_background_run(run_id: str) -> bool:
    task = _RUNS.get(run_id)
    if task is None:
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    _RUNS.pop(run_id, None)
    return True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    mode: Literal["INTRADAY", "LONGTERM"] = "LONGTERM"
    universe: Optional[list[str]] = None  # tradingsymbols; defaults to ALL_SCAN_STOCKS
    poll_interval_seconds: float = 60.0
    account_size: float = 1_000_000.0
    max_exposure: float = 1_000_000.0


class StartResponse(BaseModel):
    run_id: str


class StopRequest(BaseModel):
    run_id: str


@router.post("/start", response_model=StartResponse)
async def start_trading(req: StartRequest):
    master = InstrumentMaster(db.db)
    symbols = req.universe or list(ALL_SCAN_STOCKS)

    instruments = []
    for symbol in symbols:
        instrument = await master.get("NSE", symbol)
        if instrument is not None:
            instruments.append(instrument)
    if not instruments:
        raise HTTPException(status_code=400, detail="No resolvable instruments in universe")

    symbol_for_token = {i.instrument_token: i.tradingsymbol for i in instruments}
    strategies = [
        s for s in build_default_strategies(
            universe=[i.tradingsymbol for i in instruments], symbol_for_token=symbol_for_token,
        )
        if s.spec.mode == req.mode
    ]
    if not strategies:
        raise HTTPException(status_code=400, detail=f"No strategies registered for mode {req.mode!r}")

    feed = PollingLiveFeed(
        YFinanceProvider(), instruments, timeframe=_MODE_TIMEFRAME[req.mode],
        poll_interval_seconds=req.poll_interval_seconds,
    )
    execution = SimulatedExecutionClient()
    portfolio = Portfolio()
    ledger = LedgerStore(db.db)

    coro = run(
        strategies=strategies, feed=feed, execution=execution, portfolio=portfolio,
        clock=SystemClock(), symbol_for_token=symbol_for_token, redis=db.redis,
        account_size=req.account_size, max_exposure=req.max_exposure, ledger=ledger,
    )
    run_id = start_background_run(coro)
    logger.info("started paper-trading run %s (mode=%s, %d instruments)", run_id, req.mode, len(instruments))
    return StartResponse(run_id=run_id)


@router.post("/stop")
async def stop_trading(req: StopRequest):
    stopped = await stop_background_run(req.run_id)
    if not stopped:
        raise HTTPException(status_code=404, detail=f"No running trading run {req.run_id!r}")
    return {"run_id": req.run_id, "stopped": True}


@router.get("/positions")
async def get_positions(ledger: LedgerStore = Depends(get_ledger_store)):
    positions = await ledger.get_open_positions()
    return {symbol: position.model_dump() for symbol, position in positions.items()}


@router.get("/fills")
async def get_fills(
    symbol: Optional[str] = None,
    since: Optional[datetime] = None,
    ledger: LedgerStore = Depends(get_ledger_store),
):
    fills = await ledger.get_fills(symbol=symbol, since=since)
    return [fill.model_dump(mode="json") for fill in fills]


@router.get("/equity")
async def get_equity(ledger: LedgerStore = Depends(get_ledger_store)):
    positions = await ledger.get_open_positions()
    portfolio = Portfolio()
    portfolio.positions = positions
    # No live mark-price source wired into this read-only endpoint --
    # Portfolio.equity() falls back to each position's own avg_price when a
    # symbol isn't in mark_prices, so an empty dict here means realized P&L
    # across open positions plus zero unrealized movement, not a crash.
    equity = portfolio.equity({})
    return {"equity": equity}


@router.get("/instruments")
async def search_instruments(q: str, limit: int = 10):
    master = InstrumentMaster(db.db)
    instruments = await master.search(q, limit=limit)
    return [i.model_dump() for i in instruments]
