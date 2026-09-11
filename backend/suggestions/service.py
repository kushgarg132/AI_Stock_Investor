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
