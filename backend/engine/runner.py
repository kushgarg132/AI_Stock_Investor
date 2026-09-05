"""The bar-by-bar engine loop shared by backtest, paper, and (later) live
trading. Only the injected DataFeed/ExecutionClient/Clock differ between
them -- this function and the Strategy contract it drives don't change.
"""

import uuid
from typing import Optional

from backend.core.clock import Clock, SimClock
from backend.core.models import Intent, Order
from backend.engine.context import SimpleStrategyContext
from backend.engine.portfolio import Portfolio
from backend.engine.protocols import DataFeed, ExecutionClient, Strategy


def size_intents(intents: list[Intent], portfolio: Portfolio) -> list[Order]:
    """STUB: every Intent becomes a fixed 1-share MARKET order, regardless
    of strength/conviction or account risk.
    TODO(Task 4): replace with composite_score + risk sizing.
    """
    return [
        Order(
            id=str(uuid.uuid4()),
            symbol=intent.symbol,
            side=intent.side,
            quantity=1.0,
            order_type="MARKET",
            limit_price=None,
        )
        for intent in intents
    ]


async def run(
    strategies: list[Strategy],
    feed: DataFeed,
    execution: ExecutionClient,
    portfolio: Portfolio,
    clock: Clock,
    symbol_for_token: Optional[dict[int, str]] = None,
) -> None:
    """`symbol_for_token` is not in the plan's pseudocode signature; it's
    needed because `Bar` identifies instruments by `instrument_token` while
    Strategy/Intent/Order/StrategySpec.universe all work in tradingsymbol
    strings, and no protocol in this task carries that mapping on its own.
    Callers that already resolved an Instrument list (e.g.
    `backtest.run_backtest`) build it once and pass it in; `HistoricalFeed`
    also exposes it as `.symbol_for_token` for convenience.
    """
    symbol_for_token = symbol_for_token or {}
    ctx = SimpleStrategyContext(clock, portfolio, symbol_for_token)
    owner_by_symbol = {
        symbol: strategy for strategy in strategies for symbol in strategy.spec.universe
    }

    for strategy in strategies:
        strategy.on_start(ctx)

    async for bar in feed:
        if isinstance(clock, SimClock):
            clock.advance(bar.timestamp)
        ctx.update(bar)

        symbol = symbol_for_token.get(bar.instrument_token)

        # SimulatedExecutionClient (and any future ExecutionClient that
        # fills against the current bar rather than a live broker feed)
        # needs to know the current price; this isn't part of the shared
        # ExecutionClient protocol since a real broker client wouldn't need
        # it, so it's a best-effort duck-typed hook.
        if symbol is not None and hasattr(execution, "on_bar"):
            execution.on_bar(symbol, bar)

        if symbol is not None:
            for strategy in strategies:
                if symbol in strategy.spec.universe and bar.timeframe == strategy.spec.timeframe:
                    strategy.on_bar(ctx, bar)

        orders = size_intents(ctx.drain_intents(), portfolio)
        for order in orders:
            await execution.submit(order)

        async for fill in execution.fills():
            portfolio.apply(fill)
            owning_strategy = owner_by_symbol.get(fill.symbol)
            if owning_strategy is not None:
                owning_strategy.on_fill(ctx, fill)
