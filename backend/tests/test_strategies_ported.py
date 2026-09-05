"""Each ported strategy (backend/strategies/{longterm,intraday}/) fed a
synthetic bar sequence engineered to trigger its signal, through the
Strategy.on_bar interface directly -- no full engine run needed. Fixture
construction mirrors test_signal_integrity.py's _breakout_frame/_oversold_frame
approach, adapted to Bars instead of a DataFrame.
"""

from datetime import datetime, timedelta, timezone

from backend.core.clock import SimClock
from backend.core.models import Bar, Side
from backend.engine.context import SimpleStrategyContext
from backend.engine.portfolio import Portfolio
from backend.strategies.intraday.volume_surge import VolumeSurgeStrategy
from backend.strategies.longterm.breakout import TechnicalBreakoutStrategy
from backend.strategies.longterm.macd_crossover import MACDCrossoverStrategy
from backend.strategies.longterm.mean_reversion import MeanReversionStrategy
from backend.strategies.registry import build_default_strategies

SYMBOL = "TEST"
TOKEN = 111


def _bars(closes, opens=None, highs=None, lows=None, volumes=None, timeframe="1d",
          start=None, step=None) -> list[Bar]:
    n = len(closes)
    opens = opens or closes
    highs = highs or [c + 1 for c in closes]
    lows = lows or [c - 1 for c in closes]
    volumes = volumes if volumes is not None else [1000.0] * n
    start = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    step = step or (timedelta(days=1) if timeframe == "1d" else timedelta(minutes=5))
    return [
        Bar(
            instrument_token=TOKEN, timeframe=timeframe, timestamp=start + i * step,
            open=opens[i], high=highs[i], low=lows[i], close=closes[i], volume=volumes[i],
        )
        for i in range(n)
    ]


def _run(strategy, bars: list[Bar]):
    """Feeds every bar into a real SimpleStrategyContext (as the runner
    would), calling on_bar only for the final bar, and returns whatever
    Intents it emitted."""
    ctx = SimpleStrategyContext(SimClock(), Portfolio(), {TOKEN: SYMBOL})
    for bar in bars[:-1]:
        ctx.update(bar)
    ctx.update(bars[-1])
    strategy.on_bar(ctx, bars[-1])
    return ctx.drain_intents()


def _flat_bars(n: int, timeframe: str = "1d") -> list[Bar]:
    return _bars([100.0] * n, volumes=[1000.0] * n, timeframe=timeframe)


# ---------------------------------------------------------------------------
# TechnicalBreakoutStrategy
# ---------------------------------------------------------------------------

def _breakout_bars() -> list[Bar]:
    """A single symmetric hump (local max ~110 around index 24) followed by
    a decline back to ~90, then a final bar that breaks back above the hump
    with a volume spike -- 50 bars total, matching warmup_bars=50."""
    n = 50
    closes = []
    for i in range(n - 1):
        if i <= 24:
            closes.append(90.0 + i * (20.0 / 24.0))
        else:
            closes.append(110.0 - (i - 24) * (20.0 / 20.0))
    closes.append(115.0)  # final bar: breakout above the ~110 resistance
    volumes = [1000.0] * (n - 1) + [999_999.0]
    return _bars(closes, volumes=volumes)


def test_breakout_strategy_emits_buy_intent():
    strategy = TechnicalBreakoutStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _breakout_bars())

    assert len(intents) == 1
    intent = intents[0]
    assert intent.symbol == SYMBOL
    assert intent.side == Side.BUY
    assert intent.strength == 0.8
    assert intent.reason_codes == ["breakout_above_resistance_with_volume"]
    assert intent.stop_hint is not None
    assert intent.target_hint is not None


def test_breakout_strategy_silent_on_flat_bars():
    strategy = TechnicalBreakoutStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _flat_bars(60))
    assert intents == []


# ---------------------------------------------------------------------------
# MeanReversionStrategy
# ---------------------------------------------------------------------------

def _oversold_bars() -> list[Bar]:
    """Quiet base then a sharp selloff, mirroring
    test_signal_integrity.py::_oversold_frame."""
    closes = [100.0] * 50 + [96.0, 92.0, 88.0, 84.0, 80.0]
    return _bars(closes)


def test_mean_reversion_strategy_emits_buy_intent():
    strategy = MeanReversionStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _oversold_bars())

    assert len(intents) == 1
    intent = intents[0]
    assert intent.symbol == SYMBOL
    assert intent.side == Side.BUY
    assert intent.strength == 0.7
    assert intent.reason_codes == ["oversold_rsi_below_lower_band"]


def test_mean_reversion_strategy_silent_on_flat_bars():
    strategy = MeanReversionStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _flat_bars(60))
    assert intents == []


# ---------------------------------------------------------------------------
# MACDCrossoverStrategy
# ---------------------------------------------------------------------------

def _macd_bullish_crossover_bars() -> list[Bar]:
    """A steady decline (drives MACD histogram negative) followed by a sharp
    2-bar rally that flips the histogram positive exactly on the final bar
    (verified against the real MACD math, not guessed -- see report)."""
    decline = [140.0 - i * 2.0 for i in range(32)]  # 140 -> 78
    rally = [decline[-1] + i * 6.0 for i in range(1, 3)]  # two sharp up-bars
    closes = decline + rally
    return _bars(closes)


def test_macd_crossover_strategy_emits_bullish_buy_intent():
    strategy = MACDCrossoverStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _macd_bullish_crossover_bars())

    assert len(intents) == 1
    intent = intents[0]
    assert intent.symbol == SYMBOL
    assert intent.side == Side.BUY
    assert intent.strength == 0.75
    assert intent.reason_codes == ["macd_bullish_crossover"]


def test_macd_crossover_strategy_emits_bearish_sell_intent():
    bullish_bars = _macd_bullish_crossover_bars()
    # Mirror image: rally then sharp selloff -> histogram flips positive-to-negative.
    closes = [200.0 - (b.close - 100.0) for b in bullish_bars]
    bars = _bars(closes)

    strategy = MACDCrossoverStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, bars)

    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == Side.SELL
    assert intent.strength == 0.75
    assert intent.reason_codes == ["macd_bearish_crossover"]


def test_macd_crossover_strategy_silent_on_flat_bars():
    strategy = MACDCrossoverStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _flat_bars(40))
    assert intents == []


# ---------------------------------------------------------------------------
# VolumeSurgeStrategy
# ---------------------------------------------------------------------------

def _volume_surge_bars(bullish: bool) -> list[Bar]:
    n = 20
    closes = [100.0] * (n - 1)
    opens = [100.0] * (n - 1)
    if bullish:
        closes.append(103.0)
        opens.append(100.0)
    else:
        closes.append(97.0)
        opens.append(100.0)
    volumes = [1000.0] * (n - 1) + [10_000.0]
    return _bars(closes, opens=opens, volumes=volumes, timeframe="5m")


def test_volume_surge_strategy_emits_buy_intent_on_up_bar():
    strategy = VolumeSurgeStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _volume_surge_bars(bullish=True))

    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == Side.BUY
    assert intent.strength == 0.6
    assert intent.reason_codes == ["massive_buying_volume"]


def test_volume_surge_strategy_emits_sell_intent_on_down_bar():
    strategy = VolumeSurgeStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _volume_surge_bars(bullish=False))

    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == Side.SELL
    assert intent.strength == 0.6
    assert intent.reason_codes == ["massive_selling_volume"]


def test_volume_surge_strategy_silent_on_flat_bars():
    strategy = VolumeSurgeStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _flat_bars(25, timeframe="5m"))
    assert intents == []


# ---------------------------------------------------------------------------
# registry.build_default_strategies
# ---------------------------------------------------------------------------

def test_build_default_strategies_returns_expected_four():
    strategies = build_default_strategies(universe=[SYMBOL])
    assert len(strategies) == 4

    by_mode_timeframe = sorted((s.spec.mode, s.spec.timeframe) for s in strategies)
    assert by_mode_timeframe == [
        ("INTRADAY", "5m"),
        ("LONGTERM", "1d"),
        ("LONGTERM", "1d"),
        ("LONGTERM", "1d"),
    ]
    assert all(s.spec.universe == [SYMBOL] for s in strategies)
