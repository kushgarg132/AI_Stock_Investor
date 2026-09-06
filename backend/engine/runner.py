"""The bar-by-bar engine loop shared by backtest, paper, and (later) live
trading. Only the injected DataFeed/ExecutionClient/Clock differ between
them -- this function and the Strategy contract it drives don't change.
"""

import logging
import uuid
from typing import Optional

from backend.ai.sentiment import get_cached_sentiment
from backend.components.risk.risk import RiskRules
from backend.core.clock import Clock, SimClock
from backend.core.models import Intent, Order, Side
from backend.engine.context import SimpleStrategyContext
from backend.engine.persistence import LedgerStore
from backend.engine.portfolio import Portfolio
from backend.engine.protocols import DataFeed, ExecutionClient, Strategy, StrategyContext
from backend.engine.session import is_past_square_off_time
from backend.scoring.composite import score_intent

logger = logging.getLogger(__name__)

# % of account risked per trade at full conviction (scored.final == 1.0),
# scaled linearly down to 0 as conviction falls -- see size_intents' docstring.
BASE_RISK_PCT = 1.0


async def size_intents(
    intents: list[Intent],
    portfolio: Portfolio,
    ctx: StrategyContext,
    owner_by_symbol: dict[str, Strategy],
    redis,
    account_size: float,
    max_exposure: float,
) -> list[Order]:
    """Scores each Intent (backend.scoring.composite.score_intent, which
    caps AI's influence at AI_CAP regardless of what's passed here), then
    sizes it via the existing fixed-fractional risk sizer
    (RiskRules.calculate_position_size).

    Conviction-to-risk formula: `risk_pct = BASE_RISK_PCT * scored.final`.
    scored.final is in [0, 1] (and in practice >= 0.7*RULE_FLOOR once the
    rule floor is met, since AI can only pull it down to neutral, never
    below the rule score's floor-gated contribution) -- so this scales the
    fraction of the account risked on this trade linearly with conviction:
    full conviction (final=1.0) risks BASE_RISK_PCT of the account on a
    stop-loss-defined loss; weaker-but-still-floor-passing conviction risks
    proportionally less. Linear scaling is the simplest choice that
    guarantees the required property: `calculate_position_size` is linear
    in `risk_per_trade_percent` for fixed entry/stop/account_size, so a
    strictly higher `scored.final` can never produce a smaller position,
    all else equal.

    An Intent whose rule floor isn't met scores None and produces no order.
    An Intent with no `stop_hint` cannot be sized (no risk-per-share to
    divide by) -- skipped and logged, never guessed.

    `current_exposure` is computed fresh from `portfolio.positions` each
    call (not threaded through as mutable state), then accumulated locally
    as orders are added within this same call so a burst of same-call
    intents can't jointly blow past `max_exposure` even though each looked
    fine against the pre-call snapshot alone.
    """
    orders: list[Order] = []
    current_exposure = sum(
        abs(pos.quantity * pos.avg_price) for pos in portfolio.positions.values()
    )

    for intent in intents:
        ai_sentiment = await get_cached_sentiment(intent.symbol, redis) if redis is not None else None
        scored = score_intent(intent, ai_sentiment)
        if scored is None:
            continue  # rule floor not met -- no trade, regardless of AI

        if intent.stop_hint is None:
            logger.info("skipping intent for %s: strategy supplied no stop_hint", intent.symbol)
            continue

        history = ctx.history(intent.symbol, 1)
        if not history:
            logger.info("skipping intent for %s: no known price yet this run", intent.symbol)
            continue
        entry = history[-1].close
        stop = intent.stop_hint

        risk_pct = BASE_RISK_PCT * scored.final
        raw_size = RiskRules.calculate_position_size(account_size, risk_pct, entry, stop)
        # NSE cash equity delivery/intraday trades in whole shares only.
        size = float(int(raw_size))
        if size <= 0:
            continue

        notional = size * entry
        if not RiskRules.check_exposure_limit(current_exposure, max_exposure, notional):
            continue
        current_exposure += notional

        owning_strategy = owner_by_symbol.get(intent.symbol)
        product = "MIS" if owning_strategy is not None and owning_strategy.spec.mode == "INTRADAY" else "CNC"

        orders.append(Order(
            id=str(uuid.uuid4()),
            symbol=intent.symbol,
            side=intent.side,
            quantity=size,
            order_type="MARKET",
            limit_price=None,
            product=product,
        ))

    return orders


def _square_off_orders(
    bar_symbol: Optional[str],
    bar_timestamp,
    portfolio: Portfolio,
    owner_by_symbol: dict[str, Strategy],
) -> list[Order]:
    """MIS intraday square-off: if the strategy owning `bar_symbol` trades
    INTRADAY and the current bar is at/past 15:15 IST with an open
    position still held, force a closing MARKET order. Keyed purely off the
    bar's own timestamp, so this applies identically to a live/polling feed
    running in real time and to a HistoricalFeed backtest replaying bars
    past that time of day.
    """
    if bar_symbol is None:
        return []
    owning_strategy = owner_by_symbol.get(bar_symbol)
    if owning_strategy is None or owning_strategy.spec.mode != "INTRADAY":
        return []
    if not is_past_square_off_time(bar_timestamp):
        return []

    position = portfolio.positions.get(bar_symbol)
    if position is None or position.quantity == 0:
        return []

    closing_side = Side.SELL if position.quantity > 0 else Side.BUY
    return [Order(
        id=str(uuid.uuid4()),
        symbol=bar_symbol,
        side=closing_side,
        quantity=abs(position.quantity),
        order_type="MARKET",
        limit_price=None,
        product="MIS",
    )]


async def run(
    strategies: list[Strategy],
    feed: DataFeed,
    execution: ExecutionClient,
    portfolio: Portfolio,
    clock: Clock,
    symbol_for_token: Optional[dict[int, str]] = None,
    redis=None,
    account_size: float = 1_000_000.0,
    max_exposure: float = 1_000_000.0,
    ledger: Optional[LedgerStore] = None,
) -> None:
    """`symbol_for_token` is not in the plan's pseudocode signature; it's
    needed because `Bar` identifies instruments by `instrument_token` while
    Strategy/Intent/Order/StrategySpec.universe all work in tradingsymbol
    strings, and no protocol in this task carries that mapping on its own.
    Callers that already resolved an Instrument list (e.g.
    `backtest.run_backtest`) build it once and pass it in; `HistoricalFeed`
    also exposes it as `.symbol_for_token` for convenience.

    `redis`/`account_size`/`max_exposure` feed `size_intents` (Task 6);
    `redis=None` means sentiment is treated as neutral for every intent
    (same as a cache miss) rather than crashing -- lets backtests run
    without a Redis dependency. `ledger`, if given, mirrors every
    order/fill/position snapshot into Mongo (backend/engine/persistence.py)
    alongside the in-memory `portfolio`, which remains the book of record.
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

        orders = await size_intents(
            ctx.drain_intents(), portfolio, ctx, owner_by_symbol, redis, account_size, max_exposure,
        )
        orders.extend(_square_off_orders(symbol, bar.timestamp, portfolio, owner_by_symbol))

        for order in orders:
            if ledger is not None:
                await ledger.record_order(order)
            await execution.submit(order)

        async for fill in execution.fills():
            portfolio.apply(fill)
            if ledger is not None:
                await ledger.record_fill(fill)
                await ledger.mark_filled(fill.order_id)
            owning_strategy = owner_by_symbol.get(fill.symbol)
            if owning_strategy is not None:
                owning_strategy.on_fill(ctx, fill)

        if ledger is not None:
            await ledger.snapshot_positions(portfolio.positions)
