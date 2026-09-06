"""Current prices for a set of symbols, best-effort.

A missing quote is normal (delisted symbol, provider hiccup, market closed
on a holiday) and must never be reported as a price of zero -- callers treat
an absent symbol as "no mark", which costs them an unrealized number rather
than inventing a loss.
"""

import asyncio
import logging
from typing import Iterable

from backend.data.providers.yfinance_provider import YFinanceProvider
from backend.instruments.master import InstrumentMaster

logger = logging.getLogger(__name__)

# The P&L cards are the first thing on the statement, and they are read in a
# glance during the session. A slow upstream must cost the unrealised line,
# never the whole page: past this the marks are simply absent, which the
# callers already treat as "no mark" rather than a price of zero.
TIMEOUT_SECONDS = 4.0


async def mark_prices(db, symbols: Iterable[str]) -> dict[str, float]:
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        return {}

    master = InstrumentMaster(db)
    provider = YFinanceProvider()

    async def _one(symbol: str):
        try:
            instrument = await master.get("NSE", symbol)
            if instrument is None:
                return symbol, None
            quote = await provider.quote(instrument)
            return symbol, quote.get("last_price")
        except Exception as exc:
            logger.warning("no mark price for %s: %s", symbol, exc)
            return symbol, None

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*(_one(symbol) for symbol in symbols)), timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning("mark prices timed out for %d symbol(s)", len(symbols))
        return {}

    return {symbol: float(price) for symbol, price in results if price}
