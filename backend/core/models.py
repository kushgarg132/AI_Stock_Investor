"""Engine-core data models: plain Pydantic models / dataclasses, no I/O.

Shared by backtest, paper, and (later) live trading -- these are the only
shapes that flow through the engine loop (backend/engine/runner.py).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class Side(str, Enum):
    """Compare by identity (`side == Side.BUY`) or, once a value has round-
    tripped through something serialized (a dict/JSON), by `.value` -- never
    against a bare string literal. `SignalType.BUY` serializing to "buy" but
    being compared against "BUY" was a real P0 bug in this codebase; don't
    repeat it here."""

    BUY = "BUY"
    SELL = "SELL"


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_token: int
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Tick(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_token: int
    timestamp: datetime
    last_price: float
    volume: Optional[float] = None


@dataclass(frozen=True)
class Intent:
    """A strategy's raw trade idea, before any sizing/risk is applied.

    `__post_init__` makes "no rule hit, no intent" structural: a strategy
    literally cannot construct an Intent without at least one reason code
    and a strength in [0, 1], rather than relying on every strategy author
    remembering the convention.
    """

    symbol: str
    side: Side
    strength: float
    reason_codes: list[str]
    stop_hint: Optional[float] = None
    target_hint: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ValueError("Intent.reason_codes must not be empty -- no rule hit, no intent")
        if not (0.0 <= self.strength <= 1.0):
            raise ValueError(f"Intent.strength must be within [0, 1], got {self.strength!r}")


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    symbol: str
    side: Side
    quantity: float
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: Optional[float] = None
    status: Literal["PENDING", "FILLED", "CANCELLED", "REJECTED"] = "PENDING"
    # CNC (delivery) vs MIS (intraday, margin) -- Task 6's Indian cost model
    # (backend/engine/execution/costs.py) selects STT/brokerage rates by
    # this field. Defaults to MIS since that's what an intraday-mode
    # strategy's forced square-off order always is; size_intents (Task 6)
    # sets it explicitly per order from the owning strategy's spec.mode.
    product: Literal["CNC", "MIS"] = "MIS"


class Fill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    timestamp: datetime
    # brokerage + taxes + slippage; Task 6 owns the real cost model, this
    # task just carries the field.
    costs: float = 0.0


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
