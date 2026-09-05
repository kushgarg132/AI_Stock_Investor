"""DataFeed backed by a MarketDataProvider (Task 1): pulls each instrument's
history once up front and replays it as one chronologically-sorted Bar
stream. This is what makes backtesting possible against the yfinance
provider (or any other MarketDataProvider) that already exists.

Deviation from the brief: `MarketDataProvider.history()` (Task 1's actual
protocol, backend/data/protocols.py) takes yfinance-shaped
`interval`/`period` strings, not a `start`/`end` date range. To honor this
task's stated `HistoricalFeed(provider, instruments, date range, timeframe)`
shape without inventing a start/end-aware provider method Task 1 doesn't
have, this class still accepts `start`/`end` datetimes, requests the
broadest period ("max") from the provider, and filters the returned candles
to that closed range itself. Real intraday period limits on the actual
yfinance API aren't exercised here since tests use a fake provider.
"""

from datetime import datetime
from typing import AsyncIterator

from backend.core.models import Bar
from backend.data.protocols import MarketDataProvider
from backend.instruments.models import Instrument


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class HistoricalFeed:
    def __init__(
        self,
        provider: MarketDataProvider,
        instruments: list[Instrument],
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> None:
        self._provider = provider
        self._instruments = instruments
        self._start = start
        self._end = end
        self._timeframe = timeframe
        self.symbol_for_token: dict[int, str] = {
            instrument.instrument_token: instrument.tradingsymbol for instrument in instruments
        }

    async def __aiter__(self) -> AsyncIterator[Bar]:
        bars: list[Bar] = []
        for instrument in self._instruments:
            candles = await self._provider.history(instrument, self._timeframe, "max")
            for candle in candles:
                if not (_naive(self._start) <= _naive(candle.timestamp) <= _naive(self._end)):
                    continue
                bars.append(Bar(
                    instrument_token=instrument.instrument_token,
                    timeframe=self._timeframe,
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                ))

        bars.sort(key=lambda bar: bar.timestamp)
        for bar in bars:
            yield bar
