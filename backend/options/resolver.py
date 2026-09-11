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
