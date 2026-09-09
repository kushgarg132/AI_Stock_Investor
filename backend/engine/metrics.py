"""Backtest performance metrics computed from the `trades` list
run_backtest already builds (dicts with `realized_pnl` and `timestamp`).
Pure functions, no I/O -- separated from backtest.py so each is directly
testable against a synthetic trade list rather than a whole engine run.

Both were hardcoded 0.0 before Phase 3's backtest gate needed real numbers
to judge a strategy against.
"""

from collections import defaultdict
from datetime import datetime
from statistics import pstdev

_TRADING_DAYS_PER_YEAR = 252


def _realized_events(trades: list[dict]) -> list[float]:
    """Only fills that closed (part of) a position carry a non-zero
    realized_pnl -- opening fills are 0.0 and contribute nothing to either
    metric."""
    return [t["realized_pnl"] for t in trades if t["realized_pnl"] != 0.0]


def compute_max_drawdown(trades: list[dict], account_size: float) -> float:
    """Largest peak-to-trough drop in cumulative realized P&L, as a fraction
    of `account_size` -- the only fixed capital baseline this system tracks
    (there is no running account-equity/margin model to measure a
    peak-to-peak percentage against). Always >= 0.0."""
    events = _realized_events(trades)
    if not events or account_size <= 0:
        return 0.0

    cumulative = 0.0
    peak = 0.0
    max_drawdown_amount = 0.0
    for pnl in events:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_drawdown_amount = max(max_drawdown_amount, peak - cumulative)

    return max_drawdown_amount / account_size


def compute_sharpe_ratio(trades: list[dict], account_size: float) -> float:
    """Daily realized P&L (trades are irregular events, not fixed bars, so
    they're bucketed by calendar day first), as a fraction of
    `account_size`, annualized with sqrt(252). Risk-free rate assumed 0, the
    common simplification for a retail equity strategy. 0.0 when there are
    fewer than two days of data -- population stdev of one point is
    undefined, and dividing by it would be a crash or a fabricated number,
    not a real Sharpe ratio."""
    events = [(t["timestamp"], t["realized_pnl"]) for t in trades if t["realized_pnl"] != 0.0]
    if not events or account_size <= 0:
        return 0.0

    by_day: dict[str, float] = defaultdict(float)
    for timestamp, pnl in events:
        day = datetime.fromisoformat(timestamp).date().isoformat()
        by_day[day] += pnl

    if len(by_day) < 2:
        return 0.0

    daily_returns = [pnl / account_size for pnl in by_day.values()]
    stdev = pstdev(daily_returns)
    if stdev == 0.0:
        return 0.0

    mean_return = sum(daily_returns) / len(daily_returns)
    return (mean_return / stdev) * (_TRADING_DAYS_PER_YEAR ** 0.5)
