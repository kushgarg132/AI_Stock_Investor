"""compute_max_drawdown / compute_sharpe_ratio: the two BacktestResult
fields that were hardcoded 0.0 before Phase 3. Both take the same `trades`
shape run_backtest already builds (dicts with `realized_pnl` and
`timestamp`), so they can be tested directly against synthetic trade lists
without running the whole engine.

Drawdown is expressed as a fraction of `account_size` (the backtest's
starting capital, the only fixed baseline this system tracks -- there is no
running account-equity/margin model to measure peak-to-peak against).
Sharpe buckets realized P&L by calendar day (trades are irregular events,
not fixed bars) and annualizes with sqrt(252), risk-free rate assumed 0.
"""

from datetime import datetime, timezone

from backend.engine.metrics import compute_max_drawdown, compute_sharpe_ratio


def _trade(realized_pnl: float, day: int) -> dict:
    return {
        "realized_pnl": realized_pnl,
        "timestamp": datetime(2026, 1, day, tzinfo=timezone.utc).isoformat(),
    }


def test_no_trades_has_zero_drawdown():
    assert compute_max_drawdown([], account_size=1_000_000.0) == 0.0


def test_only_opening_fills_no_realized_pnl_has_zero_drawdown():
    trades = [_trade(0.0, 1), _trade(0.0, 2)]
    assert compute_max_drawdown(trades, account_size=1_000_000.0) == 0.0


def test_a_monotonic_gain_has_zero_drawdown():
    trades = [_trade(1000.0, 1), _trade(1000.0, 2), _trade(1000.0, 3)]
    assert compute_max_drawdown(trades, account_size=1_000_000.0) == 0.0


def test_a_loss_after_a_gain_produces_the_expected_drawdown_fraction():
    # cumulative: +10,000 -> -10,000 (a drop from peak 10,000 to -10,000,
    # i.e. a 20,000 drawdown) -> -5,000
    trades = [_trade(10_000.0, 1), _trade(-20_000.0, 2), _trade(5_000.0, 3)]
    result = compute_max_drawdown(trades, account_size=1_000_000.0)
    assert result == 0.02  # 20,000 / 1,000,000


def test_drawdown_is_always_non_negative():
    trades = [_trade(-5_000.0, 1)]  # starts with a loss, no peak to fall from
    assert compute_max_drawdown(trades, account_size=1_000_000.0) >= 0.0


def test_no_trades_has_zero_sharpe():
    assert compute_sharpe_ratio([], account_size=1_000_000.0) == 0.0


def test_a_single_days_data_has_zero_sharpe():
    """Standard deviation needs at least two data points; a single day of
    returns must not divide by zero or crash."""
    trades = [_trade(5_000.0, 1)]
    assert compute_sharpe_ratio(trades, account_size=1_000_000.0) == 0.0


def test_positive_daily_returns_give_a_positive_sharpe():
    trades = [_trade(500.0 + 100.0 * (d % 3), d) for d in range(1, 11)]  # varies, always positive
    assert compute_sharpe_ratio(trades, account_size=1_000_000.0) > 0.0


def test_negative_daily_returns_give_a_negative_sharpe():
    trades = [_trade(-500.0 - 100.0 * (d % 3), d) for d in range(1, 11)]  # varies, always negative
    assert compute_sharpe_ratio(trades, account_size=1_000_000.0) < 0.0


def test_multiple_trades_the_same_day_are_summed_before_bucketing():
    trades = [_trade(500.0, 1), _trade(500.0, 1), _trade(1000.0, 2)]
    # both days return the same +1000 -> zero variance -> zero Sharpe, not a
    # crash from dividing by a near-zero stdev.
    assert compute_sharpe_ratio(trades, account_size=1_000_000.0) == 0.0
