"""Engine-facing protocols. The whole point of this rework: backtest, paper,
and (later) live trading run the same runner.run() loop against the same
Strategy/StrategyContext contract, differing only in which DataFeed and
ExecutionClient are injected.
"""

from datetime import datetime
from typing import AsyncIterator, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict

from backend.core.models import Bar, Fill, Intent, Order, Position


class StrategySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    mode: Literal["INTRADAY", "LONGTERM"]
    timeframe: str
    warmup_bars: int
    universe: list[str]  # tradingsymbols this strategy trades


class StrategyContext(Protocol):
    def now(self) -> datetime: ...

    def history(self, symbol: str, n: int) -> list[Bar]:
        """Bars up to AND INCLUDING the current bar, never beyond -- the
        honest-backtesting contract. See backend/engine/context.py."""
        ...

    def position(self, symbol: str) -> Optional[Position]: ...
    def submit(self, intent: Intent) -> None: ...


class Strategy(Protocol):
    spec: StrategySpec

    def on_start(self, ctx: StrategyContext) -> None: ...
    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None: ...
    def on_fill(self, ctx: StrategyContext, fill: Fill) -> None: ...


class DataFeed(Protocol):
    def __aiter__(self) -> AsyncIterator[Bar]: ...


class ExecutionClient(Protocol):
    async def submit(self, order: Order) -> str: ...  # returns order id
    async def cancel(self, order_id: str) -> None: ...
    def positions(self) -> dict[str, Position]: ...
    async def fills(self) -> AsyncIterator[Fill]: ...  # fills since last call
