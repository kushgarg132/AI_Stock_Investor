# Phase 5b F&O — Cash-Secured Put Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Phase 5b F&O plumbing (widened `Instrument` model, deterministic strike/
expiry resolution, options pricing/margin estimate, lot-based sizing, expiry close-out) plus
one real LONGTERM strategy — a cash-secured put (CSP) writer — that exercises all of it end to
end through the existing human-approval suggestion pipeline.

**Architecture:** New `backend/options/` package (resolver, pricing, sizing) holds all new
option-specific logic, kept isolated from the equity-focused `size_intents`/`RiskRules` path
rather than branching deep into it. A new `CashSecuredPutStrategy` rides the *existing*,
unmodified `scan_universe` → `SuggestionSink` → `SuggestionStore` → approval-inbox pipeline.
`execute_suggestion` stays PAPER-only for every LONGTERM strategy including this one — no
`BrokerAdapter.place_order` changes are needed.

**Tech Stack:** Python 3.12, FastAPI, Motor/MongoDB (mongomock-motor in tests), pytest +
pytest-asyncio, pydantic v2.

**Spec:** `docs/superpowers/specs/2026-09-11-phase-5b-fno-cash-secured-put-design.md`

## Global Constraints

- No live broker account exists to test against — same posture as every existing broker
  adapter docstring in this codebase. Margin estimation uses only the flat-percentage
  approximation (`estimate_margin`); no live broker margin-API integration in this plan (a
  deliberate scope-down from the spec's "tries the broker's own margin endpoint first" —
  discovered during planning that this needs real per-adapter verification work the spec
  under-specified; flagged as explicit future work, not silently dropped).
- No BrokerAdapter/`place_order` changes. LONGTERM suggestions never reach a real broker
  (verified: `backend/suggestions/service.py::execute_suggestion` always synthesizes a paper
  fill), so this strategy never does either.
- `Instrument.expiry` must be typed `Optional[datetime]`, **not** `Optional[date]` — verified
  that pymongo/BSON has no native encoder for a bare `datetime.date`; `model_dump()` feeding
  `InstrumentMaster.upsert_many`'s `$set` would raise `InvalidDocument` on any row carrying a
  bare `date`. Store midnight (`datetime.combine(expiry_date, time.min)`).
- No separate `Instrument.option_type` field. Verified Kite's real instrument dump already
  populates the existing generic `instrument_type` column with `"CE"`/`"PE"`/`"FUT"` for F&O
  rows (same column equities populate with `"EQ"`) — a second field would duplicate it for no
  benefit. Use `instrument.instrument_type` wherever the spec says "option_type".
- Only `KiteInstrumentSource` (`backend/instruments/kite_source.py`) is updated to populate
  `expiry`/`strike` for NFO rows. Verified `UpstoxAdapter.instruments()` and
  `AngelOneAdapter.instruments()` (`backend/brokers/upstox.py`, `backend/brokers/angel_one.py`)
  never mapped these columns either — updating them needs a real per-broker scrip-format check
  this plan doesn't do. Kite alone is sufficient to exercise the CSP strategy end to end when
  a Kite session is connected; this is a documented scope-down, not a silent omission.
- Every existing test must keep passing unchanged after every task (`cd backend && python -m
  pytest`). New optional fields default to values that don't alter any existing code path.

---

### Task 1: Core model widening — Instrument, Order, Intent

**Files:**
- Modify: `backend/instruments/models.py`
- Modify: `backend/core/models.py:87` (`Order.product`), after `Intent`'s field block
  (`backend/core/models.py:58-64`)
- Test: `backend/tests/test_instrument_master.py`, `backend/tests/test_core_models.py`

**Interfaces:**
- Produces: `Instrument.expiry: Optional[datetime]`, `Instrument.strike: Optional[float]`
  (both default `None`); `Order.product: Literal["CNC", "MIS", "NRML"]`;
  `Intent.option_flavor: Optional[Literal["CSP"]] = None`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_instrument_master.py -- add to the existing file
from datetime import datetime

from backend.instruments.models import Instrument


def test_instrument_accepts_option_fields():
    inst = Instrument(
        exchange="NFO", tradingsymbol="RELIANCE24DEC2800PE", name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05,
        expiry=datetime(2024, 12, 26), strike=2800.0,
    )
    assert inst.expiry == datetime(2024, 12, 26)
    assert inst.strike == 2800.0


def test_instrument_option_fields_default_to_none_for_equities():
    inst = Instrument(
        exchange="NSE", tradingsymbol="RELIANCE", name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="EQ", segment="NSE",
        lot_size=1, tick_size=0.05,
    )
    assert inst.expiry is None
    assert inst.strike is None
```

```python
# backend/tests/test_core_models.py -- add to the existing file
from backend.core.models import Intent, Order, Side


def test_order_accepts_nrml_product():
    order = Order(
        id="o1", symbol="RELIANCE24DEC2800PE", side=Side.SELL, quantity=250.0,
        order_type="MARKET", limit_price=None, product="NRML",
    )
    assert order.product == "NRML"


def test_intent_option_flavor_defaults_to_none():
    intent = Intent(symbol="RELIANCE", side=Side.BUY, strength=0.7, reason_codes=["x"])
    assert intent.option_flavor is None


def test_intent_accepts_csp_option_flavor():
    intent = Intent(
        symbol="RELIANCE", side=Side.SELL, strength=0.7, reason_codes=["x"],
        option_flavor="CSP",
    )
    assert intent.option_flavor == "CSP"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_instrument_master.py tests/test_core_models.py -v`
Expected: FAIL — `Instrument`/`Order`/`Intent` reject unknown fields (`extra="forbid"`) or
`Order.product` rejects `"NRML"`.

- [ ] **Step 3: Implement**

In `backend/instruments/models.py`:

```python
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
```

In `backend/core/models.py`, change line 87:

```python
    product: Literal["CNC", "MIS", "NRML"] = "MIS"
```

And in the `Intent` dataclass (after `target_hint: Optional[float] = None` at line ~64), add:

```python
    # "CSP" (cash-secured put) marks an Intent that size_intents dispatches
    # to backend/options/sizing.py instead of the equity stop-distance
    # sizer -- see that module's docstring. None (every existing strategy)
    # means "ordinary equity intent", zero behavior change.
    option_flavor: Optional[Literal["CSP"]] = None
```

`Intent` already imports `Literal`/`Optional` at the top of `backend/core/models.py` — no new
import needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_instrument_master.py tests/test_core_models.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS — no existing test constructs `Instrument`/`Order`/`Intent` with a full
positional-arg list that a new optional field could shift (all use keyword args).

- [ ] **Step 6: Commit**

```bash
git add backend/instruments/models.py backend/core/models.py backend/tests/test_instrument_master.py backend/tests/test_core_models.py
git commit -m "feat: widen Instrument/Order/Intent for F&O (Phase 5b)"
```

---

### Task 2: Strike/expiry resolver + Kite NFO instrument mapping

**Files:**
- Create: `backend/options/__init__.py` (empty)
- Create: `backend/options/resolver.py`
- Modify: `backend/instruments/kite_source.py`
- Modify: `backend/routers/broker.py:116` (add one line after the existing NSE/BSE refresh)
- Test: `backend/tests/test_options_resolver.py` (new), `backend/tests/test_kite_instrument_source.py`

**Interfaces:**
- Consumes: `Instrument` (Task 1), `InstrumentMaster.get(exchange, tradingsymbol)` (existing,
  `backend/instruments/master.py:51-55`).
- Produces: `resolver.is_fo_eligible(symbol: str) -> bool`,
  `resolver.next_monthly_expiry(today: date, min_days_to_expiry: int = 5) -> date`,
  `resolver.nearest_strike(symbol: str, spot: float, otm_pct: float) -> float`,
  `resolver.format_tradingsymbol(underlying: str, expiry: date, strike: float, option_type: str) -> str`,
  `resolver.parse_underlying(tradingsymbol: str, expiry: date, strike: float, option_type: str) -> str`,
  `async resolver.resolve_contract(master: InstrumentMaster, underlying: str, expiry: date, strike: float, option_type: str) -> Optional[Instrument]`.

- [ ] **Step 1: Write failing tests for the pure resolver functions**

```python
# backend/tests/test_options_resolver.py
from datetime import date, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver


def test_is_fo_eligible():
    assert resolver.is_fo_eligible("RELIANCE") is True
    assert resolver.is_fo_eligible("SOME-SMALLCAP-NOT-IN-TABLE") is False


def test_next_monthly_expiry_is_last_thursday_of_month():
    # December 2024: last Thursday is the 26th.
    assert resolver.next_monthly_expiry(date(2024, 12, 1)) == date(2024, 12, 26)


def test_next_monthly_expiry_rolls_forward_when_too_close():
    # Dec 24 2024 is 2 days from the 26th -- inside the 5-day floor, rolls
    # to January 2025's last Thursday (the 30th).
    assert resolver.next_monthly_expiry(date(2024, 12, 24)) == date(2025, 1, 30)


def test_next_monthly_expiry_rolls_forward_when_already_past():
    assert resolver.next_monthly_expiry(date(2024, 12, 27)) == date(2025, 1, 30)


def test_nearest_strike_rounds_to_symbols_interval():
    # RELIANCE interval 20.0, 5% OTM below a spot of 2900 -> raw 2755, nearest
    # multiple of 20 is 2760.
    assert resolver.nearest_strike("RELIANCE", spot=2900.0, otm_pct=0.05) == 2760.0


def test_format_tradingsymbol_matches_nse_convention():
    assert resolver.format_tradingsymbol("RELIANCE", date(2024, 12, 26), 2800.0, "PE") == "RELIANCE24DEC2800PE"


def test_parse_underlying_inverts_format_tradingsymbol():
    symbol = resolver.format_tradingsymbol("RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert resolver.parse_underlying(symbol, date(2024, 12, 26), 2800.0, "PE") == "RELIANCE"


@pytest.fixture
def master():
    return InstrumentMaster(AsyncMongoMockClient()["test_db"])


@pytest.mark.asyncio
async def test_resolve_contract_finds_a_synced_nfo_row(master):
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol="RELIANCE24DEC2800PE", name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05, expiry=datetime(2024, 12, 26), strike=2800.0,
    )])
    found = await resolver.resolve_contract(master, "RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert found is not None
    assert found.lot_size == 250


@pytest.mark.asyncio
async def test_resolve_contract_returns_none_when_not_synced(master):
    found = await resolver.resolve_contract(master, "RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert found is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_options_resolver.py -v`
Expected: FAIL — `backend.options` doesn't exist yet.

- [ ] **Step 3: Implement the resolver**

`backend/options/__init__.py`: empty file.

`backend/options/resolver.py`:

```python
"""Deterministic (no live option-chain) strike/expiry selection and NFO
contract lookup for the F&O plumbing (Phase 5b). No broker account exists
to query a real option chain against -- same constraint every broker
adapter in this codebase already documents -- so strike/expiry come from a
small static table, not a live lookup. See
docs/superpowers/specs/2026-09-11-phase-5b-fno-cash-secured-put-design.md.
"""

from datetime import date, timedelta
from typing import Optional

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument

# Approximate, illustrative strike intervals for a small curated set of
# liquid NSE F&O-eligible large-caps. Not re-verified against NSE's current
# published contract specs (no network access here to do so) -- same
# "approximate, not authoritative" posture backend/engine/execution/costs.py
# already states about its own numbers.
STRIKE_INTERVALS: dict[str, float] = {
    "RELIANCE": 20.0,
    "TCS": 50.0,
    "INFY": 20.0,
    "HDFCBANK": 10.0,
    "ICICIBANK": 10.0,
    "SBIN": 10.0,
    "ITC": 5.0,
    "LT": 20.0,
    "AXISBANK": 10.0,
    "KOTAKBANK": 20.0,
}


def is_fo_eligible(symbol: str) -> bool:
    return symbol in STRIKE_INTERVALS


def _last_thursday(year: int, month: int) -> date:
    first_of_next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = first_of_next_month - timedelta(days=1)
    offset = (last_day.weekday() - 3) % 7  # Thursday == weekday 3
    return last_day - timedelta(days=offset)


def next_monthly_expiry(today: date, min_days_to_expiry: int = 5) -> date:
    """NSE equity F&O's monthly expiry: the last Thursday of the month.
    Rolls to next month if this month's has already passed, or is within
    `min_days_to_expiry` of today (too close to be worth opening a new CSP
    against)."""
    candidate = _last_thursday(today.year, today.month)
    if (candidate - today).days < min_days_to_expiry:
        year, month = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
        candidate = _last_thursday(year, month)
    return candidate


def nearest_strike(symbol: str, spot: float, otm_pct: float) -> float:
    """Rounds spot*(1 - otm_pct) to the nearest multiple of this symbol's
    strike interval. Raises KeyError for a symbol with no known interval --
    callers must check `is_fo_eligible` first."""
    interval = STRIKE_INTERVALS[symbol]
    raw = spot * (1 - otm_pct)
    return round(raw / interval) * interval


def format_tradingsymbol(underlying: str, expiry: date, strike: float, option_type: str) -> str:
    """NSE's monthly-options convention: SYMBOL + YY + MMM (upper) + STRIKE + CE/PE,
    e.g. RELIANCE24DEC2800PE."""
    strike_str = str(int(strike)) if strike == int(strike) else str(strike)
    month = expiry.strftime("%b").upper()
    year = expiry.strftime("%y")
    return f"{underlying}{year}{month}{strike_str}{option_type}"


def parse_underlying(tradingsymbol: str, expiry: date, strike: float, option_type: str) -> str:
    """Exact inverse of format_tradingsymbol -- only ever called on a
    tradingsymbol this module itself produced (via resolve_contract), never
    on an arbitrary broker-supplied one."""
    suffix = format_tradingsymbol("", expiry, strike, option_type)
    if not tradingsymbol.endswith(suffix):
        raise ValueError(f"{tradingsymbol!r} does not end with expected suffix {suffix!r}")
    return tradingsymbol[: -len(suffix)]


async def resolve_contract(
    master: InstrumentMaster, underlying: str, expiry: date, strike: float, option_type: str,
) -> Optional[Instrument]:
    """Looks up the deterministically-formatted contract in the shared
    instrument master under NFO. None means that exact contract hasn't been
    synced yet -- no broker connected, or its NFO dump doesn't (yet) carry
    this strike/expiry combination."""
    tradingsymbol = format_tradingsymbol(underlying, expiry, strike, option_type)
    return await master.get("NFO", tradingsymbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_options_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for Kite NFO mapping**

```python
# backend/tests/test_kite_instrument_source.py -- add to the existing file
from datetime import date, datetime


async def test_fetch_maps_nfo_option_rows_with_expiry_and_strike():
    from unittest.mock import MagicMock
    from backend.instruments.kite_source import KiteInstrumentSource

    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [_canned_kite_instruments_row(
        tradingsymbol="RELIANCE24DEC2800PE", exchange="NFO", segment="NFO-OPT",
        instrument_type="PE", lot_size=250, strike=2800.0, expiry=date(2024, 12, 26),
    )]
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite, exchanges=("NFO",))

    instruments = await source.fetch()

    assert len(instruments) == 1
    inst = instruments[0]
    assert inst.expiry == datetime(2024, 12, 26)
    assert inst.strike == 2800.0
    assert inst.instrument_type == "PE"


async def test_fetch_maps_equity_rows_with_no_expiry_or_strike():
    from unittest.mock import MagicMock
    from backend.instruments.kite_source import KiteInstrumentSource

    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [_canned_kite_instruments_row()]  # expiry="", strike=0.0
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite)

    instruments = await source.fetch()

    assert instruments[0].expiry is None
    assert instruments[0].strike is None
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_kite_instrument_source.py -v`
Expected: FAIL — `Instrument.expiry`/`.strike` come back `None` for the NFO row (not mapped
yet).

- [ ] **Step 7: Implement the mapping change**

In `backend/instruments/kite_source.py`, update the module docstring's last bullet and
`_to_instrument`:

```python
"""...
- `last_price` is present in Kite's row but dropped here -- volatile, no
  use for reference data. `expiry`/`strike` ARE mapped now (Phase 5b):
  the SDK's own `_parse_instruments` already parses `expiry` into a
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_kite_instrument_source.py -v`
Expected: PASS

- [ ] **Step 9: Wire the NFO sync into broker-connect**

In `backend/routers/broker.py`, right after the existing block at line 116:

```python
    count = await refresh_instruments_from_adapter(adapter)
    if count:
        logger.info("Instrument master expanded from %s: %d upserted.", broker, count)

    # Phase 5b: also pull this broker's F&O (options/futures) dump, so
    # backend.options.resolver can resolve a CSP contract without a live
    # option-chain lookup. Same best-effort posture as the NSE/BSE refresh
    # above -- refresh_instruments_from_adapter swallows its own failures.
    nfo_count = await refresh_instruments_from_adapter(adapter, exchanges=("NFO",))
    if nfo_count:
        logger.info("NFO instrument master expanded from %s: %d upserted.", broker, nfo_count)
```

- [ ] **Step 10: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add backend/options/ backend/instruments/kite_source.py backend/routers/broker.py backend/tests/test_options_resolver.py backend/tests/test_kite_instrument_source.py
git commit -m "feat: F&O strike/expiry resolver + Kite NFO instrument sync (Phase 5b)"
```

---

### Task 3: Options pricing + margin estimate

**Files:**
- Create: `backend/options/pricing.py`
- Test: `backend/tests/test_options_pricing.py`

**Interfaces:**
- Produces: `pricing.realized_volatility(closes: list[float], window: int = 20) -> float`,
  `pricing.black_scholes_put(spot: float, strike: float, days_to_expiry: int, iv: float, risk_free_rate: float = 0.07) -> float`,
  `pricing.estimate_margin(spot: float, strike: float, premium: float, lot_size: int) -> float`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_options_pricing.py
import pytest

from backend.options.pricing import black_scholes_put, estimate_margin, realized_volatility


def test_realized_volatility_of_constant_prices_is_zero():
    assert realized_volatility([100.0] * 21) == 0.0


def test_realized_volatility_is_positive_for_moving_prices():
    closes = [100.0, 102.0, 99.0, 101.0, 98.0, 103.0]
    assert realized_volatility(closes) > 0.0


def test_realized_volatility_returns_zero_for_fewer_than_two_closes():
    assert realized_volatility([100.0]) == 0.0
    assert realized_volatility([]) == 0.0


def test_black_scholes_put_deep_itm_worth_more_than_deep_otm():
    # Same spot/vol/expiry, ITM strike (2900) must price above OTM (2000).
    itm = black_scholes_put(spot=2800.0, strike=2900.0, days_to_expiry=30, iv=0.25)
    otm = black_scholes_put(spot=2800.0, strike=2000.0, days_to_expiry=30, iv=0.25)
    assert itm > otm > 0.0


def test_black_scholes_put_zero_time_to_expiry_returns_zero():
    assert black_scholes_put(spot=2800.0, strike=2800.0, days_to_expiry=0, iv=0.25) == 0.0


def test_black_scholes_put_zero_iv_returns_zero():
    assert black_scholes_put(spot=2800.0, strike=2800.0, days_to_expiry=30, iv=0.0) == 0.0


def test_estimate_margin_is_flat_percentage_of_notional():
    margin = estimate_margin(spot=2800.0, strike=2760.0, premium=45.0, lot_size=250)
    assert margin == pytest.approx(2760.0 * 250 * 0.15)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_options_pricing.py -v`
Expected: FAIL — `backend.options.pricing` doesn't exist yet.

- [ ] **Step 3: Implement**

```python
# backend/options/pricing.py
"""Black-Scholes premium estimate (using the underlying's own realized
volatility as an IV proxy, not a live option-chain quote -- no broker
account exists to query one) and a flat margin approximation. Both are
model estimates shown to a human on a LONGTERM suggestion card, never
inputs to auto-execution. See
docs/superpowers/specs/2026-09-11-phase-5b-fno-cash-secured-put-design.md.
"""

import math
from statistics import NormalDist

_NORMAL = NormalDist()


def realized_volatility(closes: list[float], window: int = 20) -> float:
    """Annualized stdev of daily log returns over the trailing `window`
    closes (or fewer if not that many are available), as an IV proxy.
    0.0 if fewer than 2 closes are available."""
    recent = closes[-(window + 1):]
    if len(recent) < 2:
        return 0.0
    log_returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
    return (variance ** 0.5) * (252 ** 0.5)


def black_scholes_put(
    spot: float, strike: float, days_to_expiry: int, iv: float, risk_free_rate: float = 0.07,
) -> float:
    """Standard Black-Scholes European put premium. Returns 0.0 for a
    non-positive time-to-expiry, volatility, spot, or strike (degenerate
    inputs, guarded rather than raising -- a caller with a stale/zero spot
    should get "no viable premium", not a crash)."""
    if days_to_expiry <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv ** 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    put = strike * math.exp(-risk_free_rate * t) * _NORMAL.cdf(-d2) - spot * _NORMAL.cdf(-d1)
    return max(put, 0.0)


# ponytail: flat approximation, no live broker margin-API call this phase.
# Upgrade path: an adapter-specific order-margin endpoint (e.g. Kite's
# basket_order_margins) once a live account exists to verify one against --
# see the plan's Global Constraints and the spec's non-goals.
MARGIN_APPROXIMATION_PCT = 0.15


def estimate_margin(spot: float, strike: float, premium: float, lot_size: int) -> float:
    """Flat percentage of contract notional (strike * lot_size) -- a
    conservative SPAN+exposure ballpark, not a real broker margin figure.
    `spot`/`premium` are accepted for interface stability (a future
    per-broker margin call will need them) but unused by this
    approximation."""
    notional = strike * lot_size
    return notional * MARGIN_APPROXIMATION_PCT
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_options_pricing.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/options/pricing.py backend/tests/test_options_pricing.py
git commit -m "feat: Black-Scholes premium estimate + margin approximation (Phase 5b)"
```

---

### Task 4: Options lot sizing

**Files:**
- Create: `backend/options/sizing.py`
- Test: `backend/tests/test_options_sizing.py`

**Interfaces:**
- Consumes: `resolver.next_monthly_expiry`, `resolver.nearest_strike`, `resolver.resolve_contract`
  (Task 2); `pricing.realized_volatility`, `pricing.black_scholes_put`, `pricing.estimate_margin`
  (Task 3); `Intent`, `Order` (Task 1); `CompositeScore` (existing, `backend/scoring/composite.py`).
- Produces: `sizing.OptionSizingResult` (frozen dataclass: `order: Order`, `contract:
  Instrument`, `premium_estimate: float`, `margin_estimate: float`, `underlying_spot: float`),
  `async sizing.size_option_intent(intent: Intent, scored: CompositeScore, ctx: StrategyContext,
  account_size: float, master: Optional[InstrumentMaster]) -> Optional[sizing.OptionSizingResult]`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_options_sizing.py
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Intent, Side
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver
from backend.options.sizing import size_option_intent
from backend.scoring.composite import CompositeScore


class _FakeCtx:
    def __init__(self, closes: list[float], now: datetime) -> None:
        self._closes = closes
        self._now = now

    def history(self, symbol: str, n: int) -> list:
        return [SimpleNamespace(close=c) for c in self._closes[-n:]]

    def now(self) -> datetime:
        return self._now


NOW = datetime(2024, 12, 1, tzinfo=timezone.utc)
CLOSES = [2900.0, 2880.0, 2910.0, 2895.0, 2905.0] * 5  # 25 bars, some variance


def _intent() -> Intent:
    return Intent(
        symbol="RELIANCE", side=Side.SELL, strength=0.8, reason_codes=["oversold_csp"],
        option_flavor="CSP",
    )


def _scored() -> CompositeScore:
    return CompositeScore(rule_score=0.8, ai_score=0.0)


@pytest.fixture
def master():
    return InstrumentMaster(AsyncMongoMockClient()["test_db"])


async def _seed_contract(master, expiry, strike) -> None:
    tradingsymbol = resolver.format_tradingsymbol("RELIANCE", expiry, strike, "PE")
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol=tradingsymbol, name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05, expiry=datetime.combine(expiry, datetime.min.time()), strike=strike,
    )])


@pytest.mark.asyncio
async def test_returns_none_when_master_is_none():
    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, None)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_contract_not_synced(master):
    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, master)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_with_fewer_than_20_bars(master):
    ctx = _FakeCtx(CLOSES[:5], NOW)
    result = await size_option_intent(_intent(), _scored(), ctx, 1_000_000.0, master)
    assert result is None


@pytest.mark.asyncio
async def test_sizes_a_resolved_contract(master):
    expiry = resolver.next_monthly_expiry(NOW.date())
    strike = resolver.nearest_strike("RELIANCE", CLOSES[-1], 0.05)
    await _seed_contract(master, expiry, strike)

    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), 1_000_000.0, master)

    assert result is not None
    assert result.order.symbol == resolver.format_tradingsymbol("RELIANCE", expiry, strike, "PE")
    assert result.order.side == Side.SELL
    assert result.order.product == "NRML"
    assert result.order.quantity == 250.0 * (result.order.quantity // 250.0)  # whole lots
    assert result.order.quantity > 0
    assert result.contract.lot_size == 250
    assert result.premium_estimate >= 0.0
    assert result.margin_estimate > 0.0
    assert result.underlying_spot == CLOSES[-1]


@pytest.mark.asyncio
async def test_returns_none_when_budget_covers_no_lots(master):
    expiry = resolver.next_monthly_expiry(NOW.date())
    strike = resolver.nearest_strike("RELIANCE", CLOSES[-1], 0.05)
    await _seed_contract(master, expiry, strike)

    result = await size_option_intent(_intent(), _scored(), _FakeCtx(CLOSES, NOW), account_size=1.0, master=master)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_options_sizing.py -v`
Expected: FAIL — `backend.options.sizing` doesn't exist yet.

- [ ] **Step 3: Implement**

```python
# backend/options/sizing.py
"""Lot-based, collateral-budget sizing for option-flavored Intents. The
equity risk-sizing path in backend/engine/runner.py::size_intents
(RiskRules.calculate_position_size, a stop-distance risk formula) has no
meaning for an option contract sized by margin/collateral instead -- this
is a deliberately separate function the runner dispatches to, rather than
a branch bolted onto that one. See
docs/superpowers/specs/2026-09-11-phase-5b-fno-cash-secured-put-design.md.
"""

import uuid
from dataclasses import dataclass
from typing import Optional

from backend.core.models import Intent, Order
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver
from backend.options.pricing import black_scholes_put, estimate_margin, realized_volatility
from backend.scoring.composite import CompositeScore

DEFAULT_PUT_OTM_PCT = 0.05
MAX_LOTS_PER_TRADE = 2
# Fraction of account_size treated as max collateral budget at full
# conviction (scored.final == 1.0), scaled linearly down like equity
# size_intents' BASE_RISK_PCT -- smaller than equity's because a CSP's
# collateral is the whole strike*lot_size, not just a stop-distance slice.
COLLATERAL_BUDGET_PCT = 0.10

_BARS_NEEDED_FOR_VOL = 20


@dataclass(frozen=True)
class OptionSizingResult:
    order: Order
    contract: Instrument
    premium_estimate: float
    margin_estimate: float
    underlying_spot: float


async def size_option_intent(
    intent: Intent,
    scored: CompositeScore,
    ctx,
    account_size: float,
    master: Optional[InstrumentMaster],
) -> Optional[OptionSizingResult]:
    """None means no order: no instrument master given, not enough price
    history for a volatility estimate, the deterministically-computed
    contract hasn't been synced from a connected broker yet, or the
    collateral budget doesn't cover even one lot."""
    if master is None:
        return None

    history = ctx.history(intent.symbol, _BARS_NEEDED_FOR_VOL)
    if len(history) < _BARS_NEEDED_FOR_VOL:
        return None
    closes = [bar.close for bar in history]
    spot = closes[-1]

    today = ctx.now().date()
    expiry = resolver.next_monthly_expiry(today)
    strike = resolver.nearest_strike(intent.symbol, spot, DEFAULT_PUT_OTM_PCT)

    contract = await resolver.resolve_contract(master, intent.symbol, expiry, strike, "PE")
    if contract is None:
        return None

    iv = realized_volatility(closes)
    days_to_expiry = (expiry - today).days
    premium = black_scholes_put(spot, strike, days_to_expiry, iv)
    margin = estimate_margin(spot, strike, premium, contract.lot_size)

    budget = account_size * (COLLATERAL_BUDGET_PCT * scored.final)
    lots = min(int(budget // max(margin, 1.0)), MAX_LOTS_PER_TRADE)
    if lots < 1:
        return None

    order = Order(
        id=str(uuid.uuid4()), symbol=contract.tradingsymbol, side=intent.side,
        quantity=float(lots * contract.lot_size), order_type="MARKET", limit_price=None,
        product="NRML",
    )
    return OptionSizingResult(
        order=order, contract=contract, premium_estimate=premium,
        margin_estimate=margin * lots, underlying_spot=spot,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_options_sizing.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/options/sizing.py backend/tests/test_options_sizing.py
git commit -m "feat: lot-based collateral-budget sizing for option intents (Phase 5b)"
```

---

### Task 5: `size_intents` dispatch branch + `Proposal.option_contract`

**Files:**
- Modify: `backend/engine/runner.py` (`Proposal` dataclass at lines 26-39, `size_intents` at
  lines 51-162, `run()` at lines 202-260 and its `size_intents` call at line ~292)
- Modify: `backend/suggestions/scan.py:76-131` (`scan_universe`'s `run()` call)
- Test: `backend/tests/test_size_intents.py`

**Interfaces:**
- Consumes: `size_option_intent`, `OptionSizingResult` (Task 4).
- Produces: `Proposal.option_contract: Optional[dict] = None`; `size_intents(..., master:
  Optional[InstrumentMaster] = None)`; `run(..., master: Optional[InstrumentMaster] = None)`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_size_intents.py -- add to the existing file
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Intent, Side
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver


class _FakeCtxWithNow:
    """Same shape as this file's existing `_FakeCtx`, plus the `.now()`
    method size_option_intent needs and per-symbol price *series* (not a
    single price) so realized_volatility has enough history to compute."""

    def __init__(self, prices: dict[str, list[float]], now: datetime) -> None:
        self._series = prices
        self._now = now

    def history(self, symbol: str, n: int) -> list:
        series = self._series.get(symbol, [])
        return [SimpleNamespace(close=c) for c in series[-n:]]

    def now(self) -> datetime:
        return self._now


NOW = datetime(2024, 12, 1, tzinfo=timezone.utc)
CLOSES = [2900.0, 2880.0, 2910.0, 2895.0, 2905.0] * 5


@pytest.mark.asyncio
async def test_option_flavored_intent_skips_equity_sizing_and_needs_no_stop_hint():
    intent = Intent(
        symbol="RELIANCE", side=Side.SELL, strength=0.8, reason_codes=["oversold_csp"],
        option_flavor="CSP",  # no stop_hint -- would be skipped by the equity path
    )
    ctx = _FakeCtxWithNow({"RELIANCE": CLOSES}, NOW)
    orders = await size_intents(
        [intent], Portfolio(), ctx, {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, master=None,
    )
    # master=None -> size_option_intent returns None -> no order, but it
    # must not fall through to the equity path and crash on stop_hint=None.
    assert orders == []


@pytest.mark.asyncio
async def test_option_flavored_intent_produces_an_order_with_a_synced_contract():
    master = InstrumentMaster(AsyncMongoMockClient()["test_db"])
    expiry = resolver.next_monthly_expiry(NOW.date())
    strike = resolver.nearest_strike("RELIANCE", CLOSES[-1], 0.05)
    tradingsymbol = resolver.format_tradingsymbol("RELIANCE", expiry, strike, "PE")
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol=tradingsymbol, name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05,
        expiry=datetime.combine(expiry, datetime.min.time()), strike=strike,
    )])

    intent = Intent(
        symbol="RELIANCE", side=Side.SELL, strength=0.8, reason_codes=["oversold_csp"],
        option_flavor="CSP",
    )
    ctx = _FakeCtxWithNow({"RELIANCE": CLOSES}, NOW)

    captured = []

    async def sink(proposal):
        captured.append(proposal)
        return False  # sink owns it, same contract as the equity/LONGTERM path

    orders = await size_intents(
        [intent], Portfolio(), ctx, {}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0, master=master, order_sink=sink,
    )

    assert orders == []  # sink took ownership
    assert len(captured) == 1
    proposal = captured[0]
    assert proposal.order.symbol == tradingsymbol
    assert proposal.order.product == "NRML"
    assert proposal.option_contract is not None
    assert proposal.option_contract["strike"] == strike
    assert proposal.option_contract["option_type"] == "PE"
    assert proposal.entry == proposal.option_contract["premium_estimate"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_size_intents.py -v`
Expected: FAIL — `Proposal` has no `option_contract` attribute; `size_intents` has no `master`
parameter and would fall through to the equity path (raising or skipping on missing
`stop_hint`, not producing the expected order/proposal).

- [ ] **Step 3: Implement**

In `backend/engine/runner.py`, add the import and extend `Proposal`:

```python
from backend.options.sizing import size_option_intent

...

@dataclass(frozen=True)
class Proposal:
    """..."""
    order: Order
    intent: Intent
    score: CompositeScore
    entry: float
    mode: str
    # Populated only for an option_flavor'd Intent (Task 5, Phase 5b):
    # strike/expiry/option_type/premium/margin/underlying_spot, so
    # SuggestionStore.create (Task 6) can persist a real contract without
    # re-deriving it. None for every ordinary equity Proposal.
    option_contract: Optional[dict] = None
```

Add `master: Optional[InstrumentMaster] = None` to `size_intents`'s signature (after
`kill_switch_tripped: bool = False,`), plus the import:

```python
from backend.instruments.master import InstrumentMaster
```

Insert the new branch immediately after the existing kill-switch check
(`if kill_switch_tripped and mode == "INTRADAY": continue`) and before the existing
`if intent.stop_hint is None:` check:

```python
        if intent.option_flavor is not None:
            result = await size_option_intent(intent, scored, ctx, account_size, master)
            if result is None:
                continue
            result.order.strategy_name = (
                owning_strategy.spec.name if owning_strategy is not None else None
            )
            option_contract = {
                "strike": result.contract.strike,
                "expiry": result.contract.expiry.isoformat() if result.contract.expiry else None,
                "option_type": result.contract.instrument_type,
                "lot_size": result.contract.lot_size,
                "premium_estimate": result.premium_estimate,
                "margin_estimate": result.margin_estimate,
                "underlying_spot": result.underlying_spot,
            }
            if order_sink is not None:
                proposal = Proposal(
                    order=result.order, intent=intent, score=scored,
                    entry=result.premium_estimate, mode=mode, option_contract=option_contract,
                )
                if not await order_sink(proposal):
                    continue
            orders.append(result.order)
            continue
```

Thread `master` through `run()`: add `master: Optional[InstrumentMaster] = None` to its
signature (alongside `kill_switch_store=None,`), and pass it at the existing `size_intents`
call site:

```python
        orders = await size_intents(
            ctx.drain_intents(), portfolio, ctx, owner_by_symbol, redis, account_size, max_exposure,
            order_sink=order_sink, per_trade_cap=per_trade_cap, kill_switch_tripped=kill_switch_tripped,
            master=master,
        )
```

In `backend/suggestions/scan.py`, pass the `master` it already constructs (line 87,
`master = InstrumentMaster(db)`) into the `run(...)` call:

```python
    await run(
        strategies=strategies,
        feed=_ArmOnFinalSession(bars, sink),
        execution=SimulatedExecutionClient(),
        portfolio=Portfolio(),
        clock=SimClock(bars[0].timestamp),
        symbol_for_token=symbol_for_token,
        redis=_ArmedOnlyRedis(redis, sink),
        account_size=account_size,
        max_exposure=max_exposure,
        ledger=None,
        order_sink=sink,
        master=master,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_size_intents.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS — every existing `size_intents`/`run()` call omits `master`, gets the `None`
default, behaves exactly as before.

- [ ] **Step 6: Commit**

```bash
git add backend/engine/runner.py backend/suggestions/scan.py backend/tests/test_size_intents.py
git commit -m "feat: dispatch option-flavored intents to options sizing in size_intents (Phase 5b)"
```

---

### Task 6: Persist `option_contract` on the suggestion document

**Files:**
- Modify: `backend/suggestions/store.py` (`SuggestionStore.create`, the `doc = {...}` block)
- Test: `backend/tests/test_suggestions.py`

**Interfaces:**
- Consumes: `Proposal.option_contract` (Task 5).
- Produces: a stored suggestion document that carries `"option_contract"` (the dict, or
  `None` for an ordinary equity suggestion).

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_suggestions.py -- add to the existing file
from backend.core.models import Order, Side


def _option_proposal() -> Proposal:  # local import of Proposal already present in this file
    return Proposal(
        order=Order(
            id="o2", symbol="RELIANCE24DEC2800PE", side=Side.SELL, quantity=250.0,
            order_type="MARKET", limit_price=None, product="NRML",
        ),
        intent=Intent(
            symbol="RELIANCE", side=Side.SELL, strength=0.8, reason_codes=["oversold_csp"],
            option_flavor="CSP",
        ),
        score=CompositeScore(rule_score=0.8, ai_score=0.0),
        entry=45.0,
        mode="LONGTERM",
        option_contract={
            "strike": 2760.0, "expiry": "2024-12-26T00:00:00", "option_type": "PE",
            "lot_size": 250, "premium_estimate": 45.0, "margin_estimate": 82800.0,
            "underlying_spot": 2900.0,
        },
    )


@pytest.mark.asyncio
async def test_create_persists_option_contract_when_present(store):
    suggestion = await store.create(user_id="alice", proposal=_option_proposal(), source="run", run_id="run-1")
    assert suggestion["option_contract"]["strike"] == 2760.0
    assert suggestion["option_contract"]["option_type"] == "PE"


@pytest.mark.asyncio
async def test_create_leaves_option_contract_none_for_equity_suggestions(store):
    suggestion = await _create(store)  # existing helper, ordinary equity Proposal
    assert suggestion["option_contract"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_suggestions.py -k option_contract -v`
Expected: FAIL — `KeyError: 'option_contract'` (not in the stored doc yet).

- [ ] **Step 3: Implement**

In `backend/suggestions/store.py::SuggestionStore.create`, add one key to the `doc = {...}`
dict (right after `"notional": order.quantity * proposal.entry,`):

```python
            "option_contract": getattr(proposal, "option_contract", None),
```

(`getattr` with a default rather than `proposal.option_contract` directly: `Proposal` always
has the attribute after Task 5, but `getattr` keeps this line safe if `create` is ever called
with an older/duck-typed proposal object in a test fixture that predates the field.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_suggestions.py -k option_contract -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/suggestions/store.py backend/tests/test_suggestions.py
git commit -m "feat: persist option_contract on suggestion documents (Phase 5b)"
```

---

### Task 7: `CashSecuredPutStrategy` + registry wiring

**Files:**
- Create: `backend/strategies/longterm/cash_secured_put.py`
- Modify: `backend/strategies/registry.py`
- Modify: `backend/tests/test_strategies_ported.py` (the hardcoded `len(strategies)` counts,
  deliberately, per this repo's own stated convention — see ROADMAP.md's Phase 4 section)
- Test: `backend/tests/test_strategies_ported.py`

**Interfaces:**
- Consumes: `resolver.is_fo_eligible` (Task 2), `Intent.option_flavor` (Task 1),
  `TokenResolvingStrategy`, `bars_to_dataframe`, `Indicators.calculate_all` (existing).
- Produces: `CashSecuredPutStrategy(universe: list[str], symbol_for_token: dict[int, str])`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_strategies_ported.py -- add near the MeanReversion tests,
# right after test_mean_reversion_strategy_silent_on_flat_bars (line ~127)
from backend.strategies.longterm.cash_secured_put import CashSecuredPutStrategy


def test_cash_secured_put_fires_on_oversold_fo_eligible_symbol():
    # RELIANCE is in resolver.STRIKE_INTERVALS (F&O-eligible); SYMBOL (this
    # file's own test constant) is not -- so this test builds its own
    # strategy/token map keyed to RELIANCE, reusing this file's existing
    # `_oversold_bars()` helper (the same fixture that already makes
    # MeanReversionStrategy fire) and `_run()`.
    strategy = CashSecuredPutStrategy(["RELIANCE"], {TOKEN: "RELIANCE"})
    intents = _run(strategy, _oversold_bars())
    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == Side.SELL
    assert intent.option_flavor == "CSP"
    assert intent.symbol == "RELIANCE"


def test_cash_secured_put_silent_for_non_fo_eligible_symbol():
    # SYMBOL (this file's own test constant, e.g. "TESTSTOCK") is not in
    # resolver.STRIKE_INTERVALS -- same oversold bars, but is_fo_eligible
    # gates it out before the RSI/Bollinger check ever runs.
    strategy = CashSecuredPutStrategy([SYMBOL], {TOKEN: SYMBOL})
    intents = _run(strategy, _oversold_bars())
    assert intents == []


def test_build_default_strategies_returns_expected_eight():
    strategies = build_default_strategies(universe=[SYMBOL])
    assert len(strategies) == 8

    by_mode_timeframe = sorted((s.spec.mode, s.spec.timeframe) for s in strategies)
    assert by_mode_timeframe == [
        ("INTRADAY", "5m"),
        ("INTRADAY", "5m"),
        ("INTRADAY", "5m"),
        ("INTRADAY", "5m"),
        ("LONGTERM", "1d"),
        ("LONGTERM", "1d"),
        ("LONGTERM", "1d"),
        ("LONGTERM", "1d"),
    ]
```

Replace the now-superseded `test_build_default_strategies_returns_expected_seven` with the
`_eight` version above (same deliberate update-not-delete convention
`test_strategies_ported.py:357-359`'s own comment already documents), and update
`test_build_default_strategies_includes_quality_momentum_when_provided`'s
`assert len(strategies) == 8` to `== 9`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_strategies_ported.py -v`
Expected: FAIL — `backend.strategies.longterm.cash_secured_put` doesn't exist; strategy counts
are still 7/8.

- [ ] **Step 3: Implement the strategy**

```python
# backend/strategies/longterm/cash_secured_put.py
"""A cash-secured put (CSP) writer: reuses MeanReversionStrategy's oversold
trigger ("price below the lower Bollinger band, RSI < 30") since "I'd be
happy to own this stock cheaper" is exactly what a CSP expresses -- but
instead of buying the underlying, it emits an option_flavor="CSP" Intent
that backend/engine/runner.py::size_intents dispatches to
backend/options/sizing.py instead of the equity stop-distance sizer.

Only fires for a symbol in backend/options/resolver.py's curated F&O-
eligible table -- most of the mid/small-cap scan universe has no listed
F&O contract at all.
"""

from backend.components.quant.indicators import Indicators
from backend.core.models import Intent, Side
from backend.engine.protocols import StrategySpec
from backend.options.resolver import is_fo_eligible
from backend.strategies.base import TokenResolvingStrategy, bars_to_dataframe


class CashSecuredPutStrategy(TokenResolvingStrategy):
    def __init__(self, universe: list[str], symbol_for_token: dict[int, str]) -> None:
        super().__init__(universe, symbol_for_token)
        self.spec = StrategySpec(
            name="cash_secured_put", mode="LONGTERM", timeframe="1d",
            warmup_bars=50, universe=universe,
        )

    def on_bar(self, ctx, bar) -> None:
        symbol = self.symbol_for(bar)
        if symbol is None or not is_fo_eligible(symbol):
            return

        history = ctx.history(symbol, self.spec.warmup_bars)
        if len(history) < self.spec.warmup_bars:
            return

        df = Indicators.calculate_all(bars_to_dataframe(history))
        current_price = df["close"].iloc[-1]
        rsi = df["rsi_14"].iloc[-1]
        lower_band = df["bb_lower"].iloc[-1]

        if not (rsi < 30 and current_price < lower_band):
            return

        ctx.submit(Intent(
            symbol=symbol, side=Side.SELL, strength=0.7,
            reason_codes=["oversold_rsi_below_lower_band"],
            # Display-only for the suggestion card, not consumed by the
            # option sizer's own strike/expiry math: the underlying levels
            # at which you'd reconsider the position early.
            stop_hint=current_price * 0.90,
            target_hint=current_price * 1.0,
            option_flavor="CSP",
        ))
```

Add to `backend/strategies/registry.py`: the import

```python
from backend.strategies.longterm.cash_secured_put import CashSecuredPutStrategy
```

and one line in the `strategies: list[Strategy] = [...]` list (after
`RSIMomentumScalpStrategy(universe, symbol_for_token),`):

```python
        CashSecuredPutStrategy(universe, symbol_for_token),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_strategies_ported.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/strategies/longterm/cash_secured_put.py backend/strategies/registry.py backend/tests/test_strategies_ported.py
git commit -m "feat: CashSecuredPutStrategy wired into the default LONGTERM set (Phase 5b)"
```

---

### Task 8: Options cost model + `execute_suggestion` options branch

**Files:**
- Create: `backend/engine/execution/options_costs.py`
- Modify: `backend/suggestions/service.py`
- Test: `backend/tests/test_options_costs.py` (new), `backend/tests/test_execute_suggestion.py`
  (new)

**Interfaces:**
- Consumes: `Side` (existing, `backend/core/models.py`).
- Produces: `options_costs.calculate_options_costs(premium: float, quantity: float, side: Side)
  -> float`; `execute_suggestion` handles a suggestion dict carrying a non-`None`
  `"option_contract"` key.

- [ ] **Step 1: Write failing test for the options cost model**

```python
# backend/tests/test_options_costs.py
from backend.core.models import Side
from backend.engine.execution.options_costs import calculate_options_costs


def test_sell_side_costs_are_positive():
    costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.SELL)
    assert costs > 0.0


def test_buy_side_costs_are_lower_than_sell_side_for_the_same_turnover():
    # STT applies to the sell/write side only, same convention the equity
    # model (calculate_indian_costs) already uses for intraday.
    buy_costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.BUY)
    sell_costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.SELL)
    assert buy_costs < sell_costs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_options_costs.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the options cost model**

```python
# backend/engine/execution/options_costs.py
"""Approximate Indian NSE options brokerage + tax cost model, applied to an
option premium fill by suggestions/service.py::execute_suggestion. Same
"approximate, not authoritative" posture backend/engine/execution/costs.py
already states about its own equity numbers -- this is a documented
simplification, not the exact regulatory formula (which also depends on
physical vs. cash settlement details this paper-only strategy doesn't
model). See docs/superpowers/specs/2026-09-11-phase-5b-fno-cash-secured-put-design.md.
"""

from backend.core.models import Side

_BROKERAGE_FLAT = 20.0
# STT on options: charged on the sell/write side only, as a percentage of
# premium turnover -- illustrative rate, not re-verified against a current
# live charge sheet (no network access here to do so).
_STT_SELL_PCT = 0.0005
_EXCHANGE_TXN_PCT = 0.00053
_GST_PCT = 0.18


def calculate_options_costs(premium: float, quantity: float, side: Side) -> float:
    """Total brokerage + statutory charges for one option fill, in rupees,
    rounded to paise. `quantity` is the total contract quantity (lots *
    lot_size), matching Order.quantity's convention for an option Order."""
    turnover = premium * quantity
    brokerage = _BROKERAGE_FLAT
    stt = turnover * _STT_SELL_PCT if side == Side.SELL else 0.0
    exchange_txn_charges = turnover * _EXCHANGE_TXN_PCT
    gst = _GST_PCT * (brokerage + exchange_txn_charges)
    return round(brokerage + stt + exchange_txn_charges + gst, 2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_options_costs.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for `execute_suggestion`'s options branch**

```python
# backend/tests/test_execute_suggestion.py
from datetime import datetime, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Side
from backend.engine.persistence import LedgerStore
from backend.suggestions.service import execute_suggestion

NOW = datetime(2024, 12, 1, tzinfo=timezone.utc)


@pytest.fixture
def ledger():
    return LedgerStore(AsyncMongoMockClient()["test_db"], user_id="alice")


def _option_suggestion() -> dict:
    return {
        "id": "s1", "symbol": "RELIANCE24DEC2800PE", "side": "SELL", "mode": "LONGTERM",
        "quantity": 250.0,
        "option_contract": {
            "strike": 2760.0, "expiry": "2024-12-26T00:00:00", "option_type": "PE",
            "lot_size": 250, "premium_estimate": 45.0, "margin_estimate": 82800.0,
            "underlying_spot": 2900.0,
        },
    }


@pytest.mark.asyncio
async def test_approving_an_option_suggestion_opens_a_short_position(ledger):
    order = await execute_suggestion(_option_suggestion(), ledger, price=45.0, now=NOW)

    assert order.symbol == "RELIANCE24DEC2800PE"
    assert order.product == "NRML"

    positions = await ledger.get_open_positions()
    position = positions["RELIANCE24DEC2800PE"]
    assert position.quantity == -250.0  # short: wrote the put
    assert position.avg_price == 45.0


@pytest.mark.asyncio
async def test_equity_suggestions_are_unaffected(ledger):
    suggestion = {
        "id": "s2", "symbol": "RELIANCE", "side": "BUY", "mode": "LONGTERM",
        "quantity": 10.0, "option_contract": None,
    }
    order = await execute_suggestion(suggestion, ledger, price=100.0, now=NOW)
    assert order.product == "CNC"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_execute_suggestion.py -v`
Expected: FAIL — `execute_suggestion` hardcodes `product = "MIS" if suggestion["mode"] ==
"INTRADAY" else "CNC"`, so the option suggestion gets `product="CNC"` (wrong), and uses
`calculate_indian_costs` (typed for `Literal["CNC","MIS"]`) unconditionally.

- [ ] **Step 7: Implement**

In `backend/suggestions/service.py`:

```python
"""Turning an approved suggestion into a real (paper) position.

The engine's own execution path fills against the bar it is currently
processing; an approval arrives out of band, minutes or hours later, so this
fills against a fresh mark instead. Everything downstream -- costs, the
ledger, the trade lifecycle -- is the same code the runner uses.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core.models import Fill, Order, Side
from backend.engine.execution.costs import calculate_indian_costs
from backend.engine.execution.options_costs import calculate_options_costs
from backend.engine.persistence import LedgerStore
from backend.engine.portfolio import Portfolio


async def execute_suggestion(
    suggestion: dict, ledger: LedgerStore, price: float, now: Optional[datetime] = None
) -> Order:
    now = now or datetime.now(timezone.utc)
    side = Side(suggestion["side"])
    is_option = suggestion.get("option_contract") is not None
    product = "NRML" if is_option else ("MIS" if suggestion["mode"] == "INTRADAY" else "CNC")
    quantity = suggestion["quantity"]

    order = Order(
        id=str(uuid.uuid4()), symbol=suggestion["symbol"], side=side, quantity=quantity,
        order_type="MARKET", limit_price=None, product=product,
    )
    await ledger.record_order(order)

    costs = (
        calculate_options_costs(price, quantity, side) if is_option
        else calculate_indian_costs(price, quantity, side, product)
    )
    fill = Fill(
        order_id=order.id, symbol=order.symbol, side=side, quantity=quantity, price=price,
        timestamp=now, costs=costs,
    )

    portfolio = Portfolio()
    portfolio.positions = await ledger.get_open_positions()
    quantity_before = portfolio.positions[order.symbol].quantity if order.symbol in portfolio.positions else 0.0
    portfolio.apply(fill)

    await ledger.on_fill(fill, quantity_before, portfolio.positions[order.symbol])
    await ledger.snapshot_positions(portfolio.positions)
    return order
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_execute_suggestion.py -v`
Expected: PASS

- [ ] **Step 9: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/engine/execution/options_costs.py backend/suggestions/service.py backend/tests/test_options_costs.py backend/tests/test_execute_suggestion.py
git commit -m "feat: options cost model + execute_suggestion options branch (Phase 5b)"
```

---

### Task 9: Expiry close-out scheduler job

**Files:**
- Modify: `backend/scheduler.py`
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `LedgerStore` (existing), `InstrumentMaster` (existing), `resolver.parse_underlying`
  (Task 2), `calculate_options_costs` (Task 8).
- Produces: `async close_expired_option_positions(db, redis=None, now=None) -> int` (count of
  positions closed); wired as a fourth step of `run_daily_jobs`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_scheduler.py -- add to the existing file
from datetime import datetime, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.engine.persistence import LedgerStore
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.prefs import PrefsStore
from backend.scheduler import close_expired_option_positions


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


async def _seed_user_with_position(mongo, tradingsymbol: str, expiry: datetime, strike: float) -> None:
    # scan_enabled_users() enumerates the real `users` collection (see
    # backend/prefs.py:55) -- a user_prefs document alone (what
    # PrefsStore.get would produce) is not enough to appear in it.
    await mongo["users"].insert_one({"id": "alice"})

    master = InstrumentMaster(mongo)
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol=tradingsymbol, name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05, expiry=expiry, strike=strike,
    )])
    ledger = LedgerStore(mongo, user_id="alice")
    await ledger.positions.insert_one({
        "user_id": "alice", "run_id": None, "symbol": tradingsymbol,
        "quantity": -250.0, "avg_price": 45.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0,
    })


@pytest.mark.asyncio
async def test_closes_an_expired_otm_position_worthless(mongo):
    # Instrument.expiry is stored/read as a NAIVE UTC datetime -- see
    # backend/instruments/kite_source.py's mapping and
    # backend/instruments/loader.py's own documented note that Motor hands
    # back naive UTC datetimes regardless of what was stored. Test fixtures
    # match that real shape rather than using a tz-aware one.
    await _seed_user_with_position(mongo, "RELIANCE24NOV2800PE", datetime(2024, 11, 28), 2800.0)

    async def fake_spot(symbol: str) -> float:
        return 3200.0  # far OTM: spot >> strike for a put

    closed = await close_expired_option_positions(
        mongo, now=datetime(2024, 12, 1, tzinfo=timezone.utc), spot_lookup=fake_spot,
    )

    assert closed == 1
    positions = await LedgerStore(mongo, user_id="alice").get_open_positions()
    assert "RELIANCE24NOV2800PE" not in positions


@pytest.mark.asyncio
async def test_leaves_unexpired_positions_untouched(mongo):
    await _seed_user_with_position(mongo, "RELIANCE25JAN2800PE", datetime(2025, 1, 30), 2800.0)

    async def fake_spot(symbol: str) -> float:
        return 3200.0

    closed = await close_expired_option_positions(
        mongo, now=datetime(2024, 12, 1, tzinfo=timezone.utc), spot_lookup=fake_spot,
    )
    assert closed == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scheduler.py -k expired -v`
Expected: FAIL — `close_expired_option_positions` doesn't exist.

- [ ] **Step 3: Implement**

In `backend/scheduler.py`, add the imports and the new function:

```python
from typing import Awaitable, Callable, Optional

from backend.core.models import Fill, Side
from backend.engine.execution.options_costs import calculate_options_costs
from backend.engine.persistence import LedgerStore
from backend.engine.portfolio import Portfolio
from backend.instruments.master import InstrumentMaster
from backend.options.resolver import parse_underlying


async def _default_spot_lookup(symbol: str) -> Optional[float]:
    # Local imports: keeps a hard `backend.database` dependency out of every
    # caller that injects its own spot_lookup (e.g. this task's tests).
    from backend.data.providers.yfinance_provider import YFinanceProvider
    from backend.database import db as _db

    instrument = await InstrumentMaster(_db.db).get("NSE", symbol)
    if instrument is None:
        return None
    quote = await YFinanceProvider().quote(instrument)
    price = quote.get("last_price")
    return float(price) if price else None


async def close_expired_option_positions(
    db,
    redis=None,
    now: Optional[datetime] = None,
    spot_lookup: Callable[[str], Awaitable[Optional[float]]] = _default_spot_lookup,
) -> int:
    """Closes every open option position (a Position whose symbol resolves
    to an NFO Instrument with expiry in the past) with a synthetic closing
    fill: worthless (premium 0) if the underlying's current mark leaves the
    put OTM, a simple intrinsic-value approximation if ITM -- not real
    physical/cash assignment mechanics, which are more involved than is
    worth modeling for a paper-only strategy. Returns the count closed."""
    now = now or datetime.now(timezone.utc)
    # Instrument.expiry round-trips through Mongo as a NAIVE UTC datetime
    # (see backend/instruments/loader.py's own note: Motor hands back naive
    # UTC datetimes regardless of what was stored) -- compare against a
    # naive `now` so this never raises on an aware-vs-naive comparison.
    now_naive = now.replace(tzinfo=None) if now.tzinfo is not None else now
    master = InstrumentMaster(db)
    prefs_store = PrefsStore(db)
    closed = 0

    for prefs in await prefs_store.scan_enabled_users():
        user_id = prefs["user_id"]
        ledger = LedgerStore(db, user_id=user_id)
        positions = await ledger.get_open_positions()

        for symbol, position in positions.items():
            contract = await master.get("NFO", symbol)
            if contract is None or contract.expiry is None:
                continue
            contract_expiry = (
                contract.expiry.replace(tzinfo=None) if contract.expiry.tzinfo is not None else contract.expiry
            )
            if contract_expiry >= now_naive:
                continue

            underlying = parse_underlying(symbol, contract.expiry.date(), contract.strike, contract.instrument_type)
            spot = await spot_lookup(underlying)
            if spot is None:
                continue

            intrinsic = max(contract.strike - spot, 0.0) if contract.instrument_type == "PE" else max(spot - contract.strike, 0.0)
            closing_side = Side.BUY if position.quantity < 0 else Side.SELL

            fill = Fill(
                order_id=str(uuid.uuid4()), symbol=symbol, side=closing_side,
                quantity=abs(position.quantity), price=intrinsic, timestamp=now,
                costs=calculate_options_costs(intrinsic, abs(position.quantity), closing_side),
            )
            portfolio = Portfolio()
            portfolio.positions = positions
            quantity_before = position.quantity
            portfolio.apply(fill)
            await ledger.on_fill(fill, quantity_before, portfolio.positions[symbol])
            await ledger.snapshot_positions(portfolio.positions)
            closed += 1

    return closed
```

Add `import uuid` alongside the existing imports at the top of `backend/scheduler.py`.

Wire it as a fourth step in `run_daily_jobs` — replace this function's existing body (the
`expired = ...` line through its final `return` and the `logger.info` call preceding it) with:

```python
async def run_daily_jobs(db, redis=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    prefs_store = PrefsStore(db)

    expired = await SuggestionStore(db).expire_stale(now=now)
    options_closed = await close_expired_option_positions(db, redis=redis, now=now)

    scanned_users = 0
    created_total = 0
    for prefs in await prefs_store.scan_enabled_users():
        user_id = prefs["user_id"]
        try:
            created = await scan_universe(
                db, user_id=user_id, universe=prefs["universe"],
                account_size=prefs["account_size"], max_exposure=prefs["max_exposure"],
                source="scheduler", redis=redis, now=now,
            )
        except Exception as exc:
            # One user's bad universe must not cancel everyone else's scan.
            logger.exception("scheduled scan failed for %s: %s", user_id, exc)
            continue

        scanned_users += 1
        created_total += len(created)
        if created:
            await attach_theses(db, user_id, created)
            await _refresh_sentiment_for(created, redis)

    logger.info(
        "daily pass: %d expired, %d option position(s) closed, %d user(s) scanned, %d suggestion(s) created",
        expired, options_closed, scanned_users, created_total,
    )
    return {
        "expired": expired, "options_closed": options_closed,
        "users": scanned_users, "created": created_total,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: daily scheduler job closes expired option positions (Phase 5b)"
```

---

## After all tasks: update ROADMAP.md

Not a numbered task (docs-only, no test cycle) — update `docs/ROADMAP.md`'s status table and
Phase 5b section the same way Phase 5a's own commits did (`b4908be`, `c8caae8`, `bbf6d03`):
mark Phase 5b's plumbing + CSP strategy done, and explicitly carry forward what's still not
done (covered call, Upstox/AngelOne NFO expiry/strike mapping, live broker margin-API
integration) as follow-up notes, not silently dropped. Commit as its own `docs:` commit, then
push.
