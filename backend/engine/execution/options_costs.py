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
