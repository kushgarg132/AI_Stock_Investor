"""QualityMomentumStrategy: fires only for symbols in the precomputed quality
universe that cross above their 200-day SMA -- same synthetic-bar harness as
test_strategies_ported.py."""

from datetime import datetime, timedelta, timezone

from backend.core.clock import SimClock
from backend.core.models import Bar, Side
from backend.engine.context import SimpleStrategyContext
from backend.engine.portfolio import Portfolio
from backend.strategies.longterm.quality_momentum import QualityMomentumStrategy

SYMBOL = "TEST"
TOKEN = 111


def _bars(closes, timeframe="1d") -> list[Bar]:
    n = len(closes)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    step = timedelta(days=1)
    return [
        Bar(
            instrument_token=TOKEN, timeframe=timeframe, timestamp=start + i * step,
            open=closes[i], high=closes[i] + 1, low=closes[i] - 1, close=closes[i],
            volume=1000.0,
        )
        for i in range(n)
    ]


def _run(strategy, bars: list[Bar]):
    ctx = SimpleStrategyContext(SimClock(), Portfolio(), {TOKEN: SYMBOL})
    for bar in bars[:-1]:
        ctx.update(bar)
    ctx.update(bars[-1])
    strategy.on_bar(ctx, bars[-1])
    return ctx.drain_intents()


def _sma200_crossover_bars() -> list[Bar]:
    """201 bars: a long decline holds price below its own SMA200, then a
    sharp final rally pushes the last close above SMA200 -- crossing on
    exactly the final bar."""
    decline = [200.0 - i * 0.5 for i in range(200)]  # 200 -> 100.5, SMA lags above price
    final = [decline[-1] + 80.0]  # sharp rally: last close jumps above the SMA
    return _bars(decline + final)


def test_fires_for_symbol_in_quality_universe_crossing_above_sma200():
    bars = _sma200_crossover_bars()
    strategy = QualityMomentumStrategy([SYMBOL], {TOKEN: SYMBOL}, quality_scores={SYMBOL: 0.72})

    intents = _run(strategy, bars)

    assert len(intents) == 1
    intent = intents[0]
    assert intent.symbol == SYMBOL
    assert intent.side == Side.BUY
    assert intent.strength == 0.72
    assert intent.reason_codes == ["quality_screen_pass", "price_above_sma200"]
    assert intent.stop_hint is not None
    assert intent.target_hint is not None


def test_silent_for_symbol_absent_from_quality_universe_same_price_action():
    bars = _sma200_crossover_bars()
    # Same universe list (so symbol_for() resolves), but no entry in quality_scores.
    strategy = QualityMomentumStrategy([SYMBOL], {TOKEN: SYMBOL}, quality_scores={})

    intents = _run(strategy, bars)

    assert intents == []


def test_silent_before_warmup():
    bars = _sma200_crossover_bars()[:150]
    strategy = QualityMomentumStrategy([SYMBOL], {TOKEN: SYMBOL}, quality_scores={SYMBOL: 0.72})

    intents = _run(strategy, bars)

    assert intents == []


def test_silent_on_flat_bars_no_crossover():
    bars = _bars([100.0] * 250)
    strategy = QualityMomentumStrategy([SYMBOL], {TOKEN: SYMBOL}, quality_scores={SYMBOL: 0.72})

    intents = _run(strategy, bars)

    assert intents == []
