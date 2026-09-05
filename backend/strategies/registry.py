"""Factory for the 4 ported strategies (Task 3), so callers -- the engine
runner, later tasks' wiring -- don't hardcode strategy construction.
"""

from typing import Optional

from backend.components.quant.indian_stocks import ALL_SCAN_STOCKS
from backend.engine.protocols import Strategy
from backend.strategies.intraday.volume_surge import VolumeSurgeStrategy
from backend.strategies.longterm.breakout import TechnicalBreakoutStrategy
from backend.strategies.longterm.macd_crossover import MACDCrossoverStrategy
from backend.strategies.longterm.mean_reversion import MeanReversionStrategy


def build_default_strategies(
    universe: Optional[list[str]] = None,
    symbol_for_token: Optional[dict[int, str]] = None,
) -> list[Strategy]:
    """`universe` defaults to `indian_stocks.ALL_SCAN_STOCKS` (the existing
    NSE mid/small-cap symbol list already used elsewhere in this codebase),
    not `backend.instruments.master` -- that's an async Mongo-backed lookup,
    and this file, like everything under backend/strategies/, must stay
    I/O-free.

    `symbol_for_token` isn't in the plan's factory pseudocode; it exists for
    the same reason `runner.run()` takes one (see its docstring) --
    `Bar.instrument_token` is all a bar carries, and `Strategy.on_bar`
    doesn't get a resolved symbol handed to it, so each strategy needs its
    own copy of that map. Callers that already built one for the runner/feed
    (e.g. `HistoricalFeed.symbol_for_token`) should pass the same dict here;
    without one, strategies simply never resolve a bar to a symbol and stay
    silent, rather than fabricating a fake token mapping.
    """
    universe = list(universe) if universe is not None else list(ALL_SCAN_STOCKS)
    symbol_for_token = symbol_for_token or {}

    return [
        TechnicalBreakoutStrategy(universe, symbol_for_token),
        MeanReversionStrategy(universe, symbol_for_token),
        MACDCrossoverStrategy(universe, symbol_for_token),
        VolumeSurgeStrategy(universe, symbol_for_token),
    ]
