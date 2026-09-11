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
# size_intents' BASE_RISK_PCT. Needs to comfortably clear one lot's
# estimate_margin (strike * lot_size * MARGIN_APPROXIMATION_PCT) for a
# typical large-cap strike against the ~1M default account_size
# (backend/prefs.py DEFAULTS) -- verified against tests/test_options_sizing.py.
COLLATERAL_BUDGET_PCT = 0.20

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
