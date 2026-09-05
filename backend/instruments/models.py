from typing import Optional

from pydantic import BaseModel, ConfigDict


class Instrument(BaseModel):
    """One row of an exchange instrument master (mirrors Kite Connect's
    /instruments CSV dump columns, minus the volatile last_price/expiry/strike
    fields which aren't needed for equity cash instruments)."""

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
