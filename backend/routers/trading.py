"""/trading/* -- paper-trading control plane and read-only ledger queries.

Every route is scoped to the authenticated user: the ledger collections are
shared, so `LedgerStore` is always constructed with `user.id` and a run can
only be stopped by the account that started it.

`start_background_run`/`stop_background_run` are deliberately factored out
of the HTTP handlers: they own nothing but the asyncio.Task bookkeeping, so
they can be unit-tested directly against a fake feed that would otherwise
run forever, without needing a real Mongo/yfinance round-trip (see
backend/tests/test_trading_router.py). `_RUNS` is what can be *cancelled*;
`RunStore` is what survives a restart and what the UI reads.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth.dependency import get_current_user
from backend.auth.kite_session import KiteSessionManager, KiteSessionState
from backend.auth.models import User
from backend.configs.settings import settings
from backend.components.quant.indian_stocks import ALL_SCAN_STOCKS
from backend.core.clock import SystemClock
from backend.database import db
from backend.data.providers.yfinance_provider import YFinanceProvider
from backend.data.feeds.live_kite import KiteTickerFeed
from kiteconnect import KiteTicker
from backend.data.feeds.polling_live import PollingLiveFeed
from backend.engine.execution.simulated import SimulatedExecutionClient
from backend.engine.persistence import LedgerStore
from backend.ws.hub import hub
from backend.ws.publish import publisher_for
from backend.engine.portfolio import Portfolio
from backend.engine.runner import run
from backend.runs import RunStore
from backend.instruments.master import InstrumentMaster
from backend.marks import mark_prices
from backend.strategies.registry import build_default_strategies
from backend.suggestions.sink import SuggestionSink
from backend.suggestions.store import SuggestionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trading", tags=["Trading"])

# run_id -> the background asyncio.Task driving that run's engine loop.
_RUNS: dict[str, asyncio.Task] = {}

_MODE_TIMEFRAME = {"INTRADAY": "5m", "LONGTERM": "1d"}


def get_ledger_store(user: User = Depends(get_current_user)) -> LedgerStore:
    return LedgerStore(db.db, user_id=user.id, on_change=publisher_for(user.id))


def get_run_store() -> RunStore:
    return RunStore(db.db)


# ---------------------------------------------------------------------------
# Background-task plumbing (testable independent of FastAPI/Mongo/yfinance)
# ---------------------------------------------------------------------------

def start_background_run(coro, run_id: Optional[str] = None, runs: Optional[RunStore] = None) -> str:
    """Schedules `coro` as a background asyncio.Task and returns a run_id
    that /trading/stop (or stop_background_run directly) can cancel by.
    Never awaits the coroutine itself -- the whole point is the HTTP
    request returns immediately even though the engine loop runs
    indefinitely against a live feed.

    `runs`, when given, is updated when the task ends on its own (crash or
    natural completion) so a dead run doesn't stay RUNNING in Mongo."""
    run_id = run_id or str(uuid.uuid4())
    task = asyncio.create_task(coro)
    _RUNS[run_id] = task

    def _cleanup(finished: asyncio.Task) -> None:
        _RUNS.pop(run_id, None)
        if runs is None:
            return
        error = None
        if not finished.cancelled():
            exception = finished.exception()
            if exception is not None:
                error = repr(exception)
        coro_ = runs.mark_error(run_id, error) if error else runs.mark_stopped(run_id)
        asyncio.create_task(coro_)

    task.add_done_callback(_cleanup)
    return run_id


async def build_feed(instruments, mode: str, poll_interval_seconds: float):
    """Real Kite ticks when a broker session is connected, polled quotes
    otherwise.

    Only intraday benefits: a ticker feed aggregates ticks into bars as they
    arrive, which is exactly what a 5-minute strategy wants and pointless for
    a daily one, where a poll of the current quote is both sufficient and
    available without a broker login.
    """
    if mode == "INTRADAY":
        session = KiteSessionManager(settings.KITE_API_KEY, settings.KITE_API_SECRET, db.redis)
        if await session.state() == KiteSessionState.ACTIVE:
            access_token = await session.get_access_token()
            tokens = [i.instrument_token for i in instruments]
            logger.info("using live Kite ticks for %d instrument(s)", len(tokens))
            return KiteTickerFeed(
                lambda: KiteTicker(api_key=settings.KITE_API_KEY, access_token=access_token),
                tokens, timeframe="5m", timeframe_seconds=300.0,
            )

    return PollingLiveFeed(
        YFinanceProvider(), instruments, timeframe=_MODE_TIMEFRAME[mode],
        poll_interval_seconds=poll_interval_seconds,
    )


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
async def start_trading(
    req: StartRequest,
    user: User = Depends(get_current_user),
    runs: RunStore = Depends(get_run_store),
):
    if settings.TRADING_LIVE_ENABLED:
        raise HTTPException(
            status_code=501,
            detail="Live order routing is not implemented; unset TRADING_LIVE_ENABLED to paper trade",
        )

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

    run_id = str(uuid.uuid4())
    feed = await build_feed(instruments, req.mode, req.poll_interval_seconds)
    execution = SimulatedExecutionClient()
    portfolio = Portfolio()
    ledger = LedgerStore(db.db, user_id=user.id, run_id=run_id, on_change=publisher_for(user.id))

    # INTRADAY orders execute themselves; LONGTERM ones stop at a PENDING
    # suggestion and wait for the user to approve or reject them.
    sink = SuggestionSink(SuggestionStore(db.db), user_id=user.id, run_id=run_id)

    coro = run(
        strategies=strategies, feed=feed, execution=execution, portfolio=portfolio,
        clock=SystemClock(), symbol_for_token=symbol_for_token, redis=db.redis,
        account_size=req.account_size, max_exposure=req.max_exposure, ledger=ledger,
        order_sink=sink,
    )
    await runs.create(
        run_id=run_id, user_id=user.id, mode=req.mode,
        universe=[i.tradingsymbol for i in instruments],
        params=req.model_dump(exclude={"universe"}),
    )
    start_background_run(coro, run_id=run_id, runs=runs)
    await hub.publish(user.id, "runs", "started", await runs.get(run_id))
    logger.info("started paper-trading run %s (mode=%s, %d instruments)", run_id, req.mode, len(instruments))
    return StartResponse(run_id=run_id)


@router.post("/stop")
async def stop_trading(
    req: StopRequest,
    user: User = Depends(get_current_user),
    runs: RunStore = Depends(get_run_store),
):
    owner = await runs.get(req.run_id)
    if owner is not None and owner["user_id"] != user.id:
        raise HTTPException(status_code=404, detail=f"No running trading run {req.run_id!r}")

    stopped = await stop_background_run(req.run_id)
    if not stopped:
        raise HTTPException(status_code=404, detail=f"No running trading run {req.run_id!r}")
    await runs.mark_stopped(req.run_id)
    await hub.publish(user.id, "runs", "stopped", await runs.get(req.run_id))
    return {"run_id": req.run_id, "stopped": True}


@router.get("/runs")
async def list_runs(
    user: User = Depends(get_current_user),
    runs: RunStore = Depends(get_run_store),
):
    """Replaces the frontend's localStorage run_id bookkeeping: the server
    knows which runs are live for this user, across reloads and devices."""
    return await runs.list_for_user(user.id)


@router.get("/positions")
async def get_positions(ledger: LedgerStore = Depends(get_ledger_store)):
    """The stored unrealized_pnl is always 0 -- the engine loop never marks a
    position to market -- so this route marks it here, at read time, with a
    best-effort live quote per symbol."""
    positions = await ledger.get_open_positions()
    quotes = await mark_prices(db.db, positions.keys())
    portfolio = Portfolio()
    portfolio.positions = positions
    portfolio.equity(quotes)
    return {symbol: position.model_dump() for symbol, position in positions.items()}


@router.get("/fills")
async def get_fills(
    symbol: Optional[str] = None,
    since: Optional[datetime] = None,
    ledger: LedgerStore = Depends(get_ledger_store),
):
    fills = await ledger.get_fills(symbol=symbol, since=since)
    return [fill.model_dump(mode="json") for fill in fills]


@router.get("/trades")
async def get_trades(
    status: Optional[Literal["OPEN", "CLOSED"]] = None,
    limit: int = 200,
    ledger: LedgerStore = Depends(get_ledger_store),
):
    """Round trips, not executions: `status=OPEN` is what the dashboard's
    Active tab shows, `CLOSED` the Completed one."""
    return await ledger.get_trades(status=status, limit=limit)


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
