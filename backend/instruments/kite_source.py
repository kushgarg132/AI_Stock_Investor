"""InstrumentSource (backend/instruments/loader.py) backed by Kite Connect's
real instrument dump: `KiteConnect.instruments(exchange)` -> GET
https://api.kite.trade/instruments/{exchange} ("market.instruments" in the
SDK's route table), which the SDK parses from Kite's CSV response into a
list of dicts.

Field-mapping note (per the task brief -- Kite's dict keys mostly line up
with `Instrument`'s fields already, but not entirely):
- `instrument_token`, `lot_size` come back as `int` and `tick_size` as
  `float` -- the SDK's own `_parse_instruments` already casts these.
- `exchange_token` is NOT cast by the SDK (it stays a CSV string, e.g.
  `"408065"`) even though every other numeric column is -- verified against
  pykiteconnect 5.2.1's `connect.py::_parse_instruments`. This module casts
  it to `int` explicitly since `Instrument.exchange_token` is typed `int`.
- Kite's dump has no ISIN column at all -- `Instrument.isin` is left `None`
  (it's `Optional` for exactly this reason per `Instrument`'s docstring).
- `last_price`, `expiry`, `strike` are present in Kite's row but dropped
  here -- `Instrument` deliberately excludes them (see its docstring).
"""

import asyncio
from typing import Callable

from backend.instruments.models import Instrument


class KiteInstrumentSource:
    def __init__(
        self,
        kite_client_factory: Callable[[], "KiteConnect"],  # noqa: F821
        exchanges: tuple[str, ...] = ("NSE",),
    ) -> None:
        self._kite_client_factory = kite_client_factory
        self._exchanges = exchanges

    async def fetch(self) -> list[Instrument]:
        kite = self._kite_client_factory()
        rows = []
        for exchange in self._exchanges:
            rows.extend(await asyncio.to_thread(kite.instruments, exchange))
        return [self._to_instrument(row) for row in rows]

    @staticmethod
    def _to_instrument(row: dict) -> Instrument:
        return Instrument(
            exchange=row["exchange"],
            tradingsymbol=row["tradingsymbol"],
            name=row["name"],
            instrument_token=int(row["instrument_token"]),
            exchange_token=int(row["exchange_token"]),
            instrument_type=row["instrument_type"],
            segment=row["segment"],
            lot_size=int(row["lot_size"]),
            tick_size=float(row["tick_size"]),
        )
