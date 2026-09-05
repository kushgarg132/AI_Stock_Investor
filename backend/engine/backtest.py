"""Wires HistoricalFeed + SimClock + SimulatedExecutionClient + Portfolio
through the shared runner.run() loop, then reports through the existing
(until now referenced nowhere) `BacktestResult` model.
"""

from datetime import datetime

from backend.components.shared.models import BacktestResult
from backend.core.clock import SimClock
from backend.data.feeds.historical import HistoricalFeed
from backend.data.protocols import MarketDataProvider
from backend.engine.execution.simulated import SimulatedExecutionClient
from backend.engine.portfolio import Portfolio
from backend.engine.protocols import Strategy
from backend.engine.runner import run
from backend.instruments.models import Instrument


async def run_backtest(
    strategies: list[Strategy],
    provider: MarketDataProvider,
    instruments: list[Instrument],
    start: datetime,
    end: datetime,
    timeframe: str,
    account_size: float = 1_000_000.0,
    max_exposure: float = 1_000_000.0,
) -> BacktestResult:
    feed = HistoricalFeed(provider, instruments, start, end, timeframe)
    execution = SimulatedExecutionClient()
    portfolio = Portfolio()
    clock = SimClock()

    trades: list[dict] = []
    original_fills = execution.fills

    async def recording_fills():
        # Trade-log bookkeeping belongs here, not on Portfolio/ExecutionClient
        # (both shared with paper/live trading). Peeking at `portfolio`
        # right before and right after the fill is yielded works because the
        # runner applies the fill to `portfolio` between one `yield` and the
        # generator's next resumption.
        async for fill in original_fills():
            pre = portfolio.positions.get(fill.symbol)
            pre_realized = pre.realized_pnl if pre else 0.0
            yield fill  # runner calls portfolio.apply(fill) here
            post = portfolio.positions[fill.symbol]
            trades.append({
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "timestamp": fill.timestamp.isoformat(),
                "costs": fill.costs,
                "realized_pnl": post.realized_pnl - pre_realized,
            })

    execution.fills = recording_fills  # type: ignore[method-assign]

    await run(
        strategies=strategies,
        feed=feed,
        execution=execution,
        portfolio=portfolio,
        clock=clock,
        symbol_for_token=feed.symbol_for_token,
        account_size=account_size,
        max_exposure=max_exposure,
    )

    total_trades = len(trades)
    total_pnl = sum(t["realized_pnl"] for t in trades)
    closed_trades = [t for t in trades if t["realized_pnl"] != 0.0]
    win_rate = (
        sum(1 for t in closed_trades if t["realized_pnl"] > 0) / len(closed_trades)
        if closed_trades
        else 0.0
    )
    gross_profit = sum(t["realized_pnl"] for t in closed_trades if t["realized_pnl"] > 0)
    gross_loss = -sum(t["realized_pnl"] for t in closed_trades if t["realized_pnl"] < 0)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    return BacktestResult(
        symbol=",".join(instrument.tradingsymbol for instrument in instruments),
        start_date=start,
        end_date=end,
        total_trades=total_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_pnl=total_pnl,
        # Both need a per-bar equity curve the runner doesn't expose yet;
        # follow-up, not computed here (see task-2-report.md).
        max_drawdown=0.0,
        sharpe_ratio=0.0,
        trades=trades,
    )
