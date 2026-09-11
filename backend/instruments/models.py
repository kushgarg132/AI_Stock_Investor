from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Instrument(BaseModel):
    """One row of an exchange instrument master (mirrors Kite Connect's
    /instruments CSV dump columns). `expiry`/`strike` are populated for F&O
    (NFO) rows and None for equity cash instruments; `instrument_type`
    already carries CE/PE/FUT/EQ, so there is no separate option_type
    field."""

    model_config = ConfigDict(extra="forbid")

    exchange: str
    tradingsymbol: str
    name: str
    instrument_token: int
    exchange_token: int
    instrument_type: str
    segment: str
    lot_size: int
    tick_size: float
    isin: Optional[str] = None
    expiry: Optional[datetime] = None
    strike: Optional[float] = None
