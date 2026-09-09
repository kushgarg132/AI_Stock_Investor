# Live equity execution — design

Phase 5a of `docs/ROADMAP.md` ("Phase 5 — Live execution + F&O", scoped down). Real broker
order placement for equities, on top of everything already built (multi-tenancy, broker
adapters, kill-switch, backtest gate, capital caps). F&O (options/futures, lot/margin-aware
sizing, widened `Instrument` model) is deliberately **out of scope** here — its own spec,
once this is proven, per Phase 5's original "Instrument model widens to
(symbol, exchange, instrument_type, lot_size, expiry, strike, option_type)" item.

## Why this scope split

Phase 5 as originally written bundles live equity execution and F&O into one phase. They're
separable: F&O sizing/margin logic depends on live execution existing first, but live equity
execution stands on its own and is independently valuable (and testable, to the extent
anything here is testable without a funded live account). Splitting lets this land and prove
itself before the harder F&O modeling work starts.

## Current state (why each piece is needed)

- `ExecutionClient` (`backend/engine/protocols.py:49-53`) has exactly one implementation,
  `SimulatedExecutionClient` — fills MARKET orders instantly at the current bar's close, no
  real broker involved. `runner.run()` is already broker-agnostic; it only knows the
  `ExecutionClient` protocol.
- `BrokerAdapter` (`backend/brokers/protocol.py`) currently covers session lifecycle and
  market data (`history`, `quote`, `instruments`, `ticker_feed`) for Kite/Upstox/Angel One.
  It has **no order-placement surface at all** — nothing in this codebase has ever placed a
  real order.
- `/trading/start` hard-blocks on `settings.TRADING_LIVE_ENABLED` with a 501
  ("Live order routing is not implemented") — a single global dead-man's switch, not a
  per-user or per-strategy decision.
- `Order` (`backend/core/models.py`) has no field identifying which strategy emitted it —
  needed both for per-strategy live/paper routing and for the ledger to attribute a live
  fill correctly.
- Phase 3's kill-switch, per-trade cap, and daily-loss-limit, and Phase 3/4's backtest gate,
  all sit in `size_intents`/`run()` **upstream** of `ExecutionClient.submit()`. They apply to
  whatever `ExecutionClient` is wired in, live included, with no changes needed here.
- No live broker account is connected to this deployment today. Every broker adapter in this
  codebase (Phase 2) was written and "verified" against each broker's own documentation, not
  a live account — this phase's order-placement code will carry the same caveat and say so
  in its own docstrings, same as Phase 2 did.

## Architecture

```
runner.run()
  -> size_intents()  [kill-switch / caps / gate already applied here, unchanged]
  -> RoutingExecutionClient.submit(order)
       order.strategy_name in user's live_strategies
         AND broker session ACTIVE
         AND strategy passed the backtest gate
       -> yes: BrokerExecutionClient.submit(order)  [real broker]
       -> no:  SimulatedExecutionClient.submit(order)  [paper, unchanged]
```

Any doubt routes to paper. There is no path where a strategy trades live because of a
missing check — every condition must be affirmatively true.

### 1. `Order` gains `strategy_name`

`backend/core/models.py`. `size_intents` already computes `owning_strategy` per intent
(`backend/engine/runner.py:99-100`); it starts setting `strategy_name=owning_strategy.spec.name`
on the `Order` it builds. Existing callers (backtest, tests) unaffected — it's a plain
required field, not optional, since every order must be attributable.

### 2. `BrokerAdapter` gains order operations

`backend/brokers/protocol.py`:

```python
async def place_order(self, order: Order) -> str: ...        # returns broker order id
async def cancel_order(self, broker_order_id: str) -> None: ...
async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus: ...
async def get_positions(self) -> dict[str, Position]: ...      # broker's own book
```

`BrokerOrderStatus` (new model, `backend/core/models.py`): `status` (one of the order state
machine's values below), `filled_quantity`, `average_price`, `broker_order_id`.

Implemented for all three brokers (`kite.py`, `upstox.py`, `angel_one.py`), MARKET orders
only for v1 — matches `SimulatedExecutionClient`'s existing limitation, and LIMIT order
lifecycle (partial fills over time, amend, etc.) is real extra complexity deferred
deliberately. Each adapter's docstring states plainly this is unverified against a live
account, same convention as Phase 2.

### 3. Order state machine + `LiveOrderStore`

States: `SUBMITTED -> ACKNOWLEDGED -> PARTIALLY_FILLED -> FILLED` / `REJECTED` / `CANCELLED`.

New collection `live_orders`, one document per submitted live order: `{order_id (app-side,
== Order.id), broker_order_id, user_id, strategy_name, symbol, status, filled_quantity,
average_price, submitted_at, updated_at}`.

**Idempotent submission**: before calling `adapter.place_order`, `BrokerExecutionClient`
checks `LiveOrderStore` for an existing `order_id -> broker_order_id` mapping. Found: return
the existing `broker_order_id`, don't resubmit. Not found: place, then record the mapping
*before* returning — so a crash between "broker accepted the order" and "we recorded that"
is the one gap this can't close (a broker-side idempotency key would close it, but none of
the three brokers here support one on this endpoint shape; noting as a known gap, not
solving it in v1).

**Status polling**: a background task (same shape as `PollingLiveFeed`'s existing poll loop)
ticks every N seconds for each `SUBMITTED`/`ACKNOWLEDGED`/`PARTIALLY_FILLED` order, calls
`get_order_status`, updates `LiveOrderStore`, and — on a new `FILLED`/`PARTIALLY_FILLED`
delta — synthesizes a `Fill` that flows through the same `execution.fills()` ->
`portfolio.apply()` path paper fills already use, so `on_fill` strategy hooks and the ledger
don't need to know the difference. Broker websocket order postbacks (Kite supports these)
would be lower-latency but are out of scope for v1 — polling is simpler and this app already
has the pattern.

### 4. `BrokerExecutionClient(ExecutionClient)`

`backend/engine/execution/broker.py`. Implements the four `ExecutionClient` methods against
one `BrokerAdapter` + `LiveOrderStore`:

- `submit`: the idempotent-submit flow above, records `SUBMITTED`, returns `order.id`.
- `cancel`: looks up `broker_order_id`, calls `adapter.cancel_order`.
- `positions`: proxies `adapter.get_positions()` — this is what reconciliation reads.
- `fills`: an async generator fed by the poll loop's synthesized fills (mirrors
  `SimulatedExecutionClient`'s `_pending_fills` queue shape).

### 5. `RoutingExecutionClient(ExecutionClient)`

`backend/engine/execution/routing.py`. Constructed per run with `paper` (a
`SimulatedExecutionClient`), a `dict[str, BrokerExecutionClient]` keyed by strategy name
(only for strategies that actually cleared all three live conditions — built once at
`/trading/start`, not re-evaluated mid-run), and dispatches each method by
`order.strategy_name`. `positions()`/`fills()` merge both sources.

### 6. Per-user, per-strategy live toggle

New pref `live_strategies: list[str]` in `PrefsStore` (default `[]` — new and existing users
start fully paper; no silent opt-in). Settings -> Mandate gets a per-strategy toggle list
(strategy names from `build_default_strategies`), same interaction pattern as `scan_enabled`'s
existing on/off pill.

`/trading/start` builds the live set as:

```python
live_eligible = await live_eligible_strategies(candidate_strategies, gate)  # Phase 4, unchanged
broker_active = await adapter.state() == BrokerSessionState.ACTIVE if adapter else False
live_strategy_names = {
    s.spec.name for s in live_eligible
    if s.spec.name in prefs["live_strategies"] and broker_active
}
```

`RoutingExecutionClient` is built with `BrokerExecutionClient` instances only for
`live_strategy_names`; every other strategy in the run — including one the user toggled live
but whose broker isn't `ACTIVE`, or that hasn't cleared the gate — routes through paper.
Replaces the `TRADING_LIVE_ENABLED` 501 block entirely.

### 7. Reconciliation

On `/trading/start`, for each strategy actually going live (`live_strategy_names` non-empty),
before the run loop starts: call `adapter.get_positions()` and merge into `Portfolio` (broker
quantity/avg_price wins over any stale local record — there shouldn't be one, since a fresh
run starts a fresh in-memory `Portfolio`, but the *ledger's* last-known state could disagree
after a restart, and the broker is truth). Same call also runs on each status-poll tick, so
drift (a fill NeoTrade's poll missed, a manual trade the user placed in the broker's own app)
self-corrects rather than compounding silently.

## Error handling

- `place_order` raising (network, broker 4xx/5xx): the order stays out of `LiveOrderStore`
  entirely (never recorded as `SUBMITTED`) so a retry is a fresh idempotent-submit check that
  correctly finds nothing and tries again — no zombie `SUBMITTED` row for an order the broker
  never actually saw.
- `get_order_status` raising mid-poll for one order: log and continue to the next order in
  the poll batch; don't let one broker hiccup stall status updates for every other live order.
- A `REJECTED` broker order status: `BrokerExecutionClient.fills()` never yields a `Fill` for
  it (nothing to apply to `Portfolio`); the `live_orders` row's `status` is the only record,
  surfaced wherever the frontend already shows order/trade history.

## Testing

- `BrokerExecutionClient`/`RoutingExecutionClient`/`LiveOrderStore` against fake
  `BrokerAdapter`s (same style as existing broker adapter tests) — no real network, ever.
- Idempotent-submit: two `submit()` calls with the same `Order.id` result in exactly one
  `place_order` call.
- Routing: a strategy in `live_strategies` but with an inactive broker session routes to
  paper, proven by a test — this is the single most safety-critical behavior in the whole
  design and gets the most explicit coverage.
- Reconciliation: broker positions differing from local `Portfolio` after a simulated
  restart get overwritten by the broker's numbers, proven by a test.
- No integration test against a real broker exists or can exist yet (no live account) — this
  matches every other broker-facing test in this codebase today.

## Done when

A `BrokerExecutionClient`-routed order reaches `adapter.place_order` (proven against a fake
adapter, not a real account); a strategy toggled live with no active broker session
demonstrably routes to paper; reconciliation overwrites a stale local position with the
broker's own on run start; `TRADING_LIVE_ENABLED`/the 501 block is gone from
`/trading/start`. Verifying an order *actually* reaches a real broker's order book is
explicitly **not** part of "done" here — no live account exists to check that against.
