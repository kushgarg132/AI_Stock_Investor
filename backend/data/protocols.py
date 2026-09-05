from typing import Protocol

from backend.components.shared.models import PriceCandle
from backend.instruments.models import Instrument


class MarketDataProvider(Protocol):
    async def history(self, instrument: Instrument, interval: str, period: str) -> list[PriceCandle]: ...
    async def quote(self, instrument: Instrument) -> dict: ...  # last price, ohlc, volume
