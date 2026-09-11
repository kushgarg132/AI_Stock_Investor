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
- `last_price` is present in Kite's row but dropped here -- volatile, no
  use for reference data. `expiry`/`strike` ARE mapped now (Phase 5b): the
  SDK's own `_parse_instruments` already parses `expiry` into a
  `datetime.date` when present (empty string for equities, left
  unconverted) and `strike` into a `float` (0.0 for equities) -- verified
  against the installed pykiteconnect package's `connect.py::
  _parse_instruments` source directly. `Instrument.expiry` is typed
  `datetime` (not `date`) since bson/pymongo has no native `date` codec;
  this module converts at the boundary.
"""

import asyncio
from datetime import date, datetime, time
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
        raw_expiry = row["expiry"]
        expiry = datetime.combine(raw_expiry, time.min) if isinstance(raw_expiry, date) else None
        strike = float(row["strike"]) if row.get("strike") else None
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
            expiry=expiry,
            strike=strike,
        )
