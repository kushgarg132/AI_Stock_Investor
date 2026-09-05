"""The single most important test in this task: StrategyContext.history()
must never expose a bar beyond the one currently being processed. The
buffer is fed one bar at a time by `update()`, so a future bar simply isn't
in the list yet -- not "trust the docstring," but structurally enforced.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.clock import SimClock
from backend.core.models import Bar
from backend.engine.context import SimpleStrategyContext
from backend.engine.portfolio import Portfolio

TOKEN = 1
SYMBOL = "TEST"


def _bar(i: int, ts: datetime) -> Bar:
    price = 100.0 + i
    return Bar(
        instrument_token=TOKEN, timeframe="1d", timestamp=ts,
        open=price, high=price + 1, low=price - 1, close=price, volume=1000.0,
    )


def test_history_never_sees_a_future_bar():
    ctx = SimpleStrategyContext(SimClock(), Portfolio(), {TOKEN: SYMBOL})
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(i, base + timedelta(days=i)) for i in range(5)]

    for i, bar in enumerate(bars):
        ctx.update(bar)
        seen = ctx.history(SYMBOL, n=100)

        assert len(seen) == i + 1, "history must contain exactly the bars processed so far"
        assert seen[-1] == bar, "the most recent bar must be the one just processed"

        # Deliberately try to read past the current bar: there is no i+1'th
        # element because it hasn't been fed to the context yet.
        with pytest.raises(IndexError):
            _ = seen[i + 1]


def test_history_respects_n_and_unknown_symbol():
    ctx = SimpleStrategyContext(SimClock(), Portfolio(), {TOKEN: SYMBOL})
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        ctx.update(_bar(i, base + timedelta(days=i)))

    assert len(ctx.history(SYMBOL, n=2)) == 2
    assert ctx.history(SYMBOL, n=0) == []
    assert ctx.history("UNKNOWN", n=10) == []
