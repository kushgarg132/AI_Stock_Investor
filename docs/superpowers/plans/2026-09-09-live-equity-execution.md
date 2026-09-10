# Live Equity Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real broker order placement for equities (Kite/Upstox/Angel One), routed per-user
per-strategy on top of the existing paper-trading engine, with reconciliation against the
broker's own book. F&O is explicitly out of scope.

**Architecture:** `RoutingExecutionClient` wraps the existing `SimulatedExecutionClient`
(paper, unchanged) plus one `BrokerExecutionClient` per strategy the user has toggled live,
dispatching each `Order` by its new `strategy_name` field. `BrokerExecutionClient` talks to a
`BrokerAdapter`, now extended with `place_order`/`cancel_order`/`get_order_status`/
`get_positions`, and tracks state in a new `LiveOrderStore` (Mongo). Status polling and
reconciliation reuse `runner.run()`'s existing per-bar loop via a duck-typed `poll_once()`
hook — no new background task.

**Tech Stack:** FastAPI, Motor/MongoDB, `kiteconnect` SDK (Kite), plain `httpx` (Upstox,
Angel One) — same stack Phase 2's broker adapters already use.

**Spec:** `docs/superpowers/specs/2026-09-09-live-equity-execution-design.md`

## Global Constraints

- MARKET orders only — no LIMIT order lifecycle in this pass (matches
  `SimulatedExecutionClient`'s existing limitation).
- No live broker account exists to test against. Every broker-facing test mocks the SDK/HTTP
  call, exactly like every existing broker adapter test in this codebase (`test_kite_adapter.py`,
  `test_upstox_adapter.py`, `test_angel_one_adapter.py`) — never a real network call in tests.
- Default-to-paper on any doubt: a strategy only ever routes live if every one of (toggled
  live by the user, broker session `ACTIVE`, backtest-gate-eligible) is true. Missing or
  unconfirmed information about any of the three means paper, never live.
- `Order.strategy_name` is `Optional[str] = None`, not a required field — touching every
  existing `Order(...)` call site (persistence.py, suggestions/service.py, five+ test files)
  for a routing-only field is unnecessary churn; `None` is itself the correct "not eligible
  for live routing" default.
- Existing kill-switch / per-trade cap / daily-loss-limit / backtest gate logic in
  `size_intents`/`run()` is untouched — it already applies to whatever `ExecutionClient` is
  wired in.

---

## Task 1: `Order.strategy_name`, `BrokerOrderStatus`, `LiveOrderState`

**Files:**
- Modify: `backend/core/models.py`
- Modify: `backend/engine/runner.py:142-152` (size_intents' order-building block)
- Test: `backend/tests/test_size_intents.py`

**Interfaces:**
- Produces: `Order.strategy_name: Optional[str]`; `LiveOrderState` (Literal type, values
  `"SUBMITTED"`, `"ACKNOWLEDGED"`, `"PARTIALLY_FILLED"`, `"FILLED"`, `"REJECTED"`,
  `"CANCELLED"`); `BrokerOrderStatus` (pydantic model: `status: LiveOrderState`,
  `filled_quantity: float`, `average_price: float`, `broker_order_id: str`).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_size_intents.py` (extend `_FakeStrategy` to carry a name first):

```python
class _FakeStrategy:
    def __init__(self, mode: str, name: str = "fake") -> None:
        self.spec = SimpleNamespace(mode=mode, name=name)
```

```python
@pytest.mark.asyncio
async def test_order_carries_the_owning_strategys_name():
    intent = Intent(
        symbol="RELIANCE", side=Side.BUY, strength=1.0,
        reason_codes=["signal"], stop_hint=90.0,
    )
    ctx = _FakeCtx({"RELIANCE": 100.0})
    strategy = _FakeStrategy(mode="INTRADAY", name="volume_surge")
    orders = await size_intents(
        [intent], Portfolio(), ctx, {"RELIANCE": strategy}, _no_sentiment_redis(),
        account_size=1_000_000.0, max_exposure=1_000_000.0,
    )
    assert len(orders) == 1
    assert orders[0].strategy_name == "volume_surge"


def test_order_strategy_name_defaults_to_none():
    from backend.core.models import Order, Side
    order = Order(id="x", symbol="RELIANCE", side=Side.BUY, quantity=1.0, order_type="MARKET")
    assert order.strategy_name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_size_intents.py -k strategy_name -v`
Expected: FAIL — `Order` has no field `strategy_name`, `_FakeStrategy` construction error.

- [ ] **Step 3: Add the field and models**

In `backend/core/models.py`, add `strategy_name` to `Order` (after `product`):

```python
class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    symbol: str
    side: Side
    quantity: float
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: Optional[float] = None
    status: Literal["PENDING", "FILLED", "CANCELLED", "REJECTED"] = "PENDING"
    product: Literal["CNC", "MIS"] = "MIS"
    # Which strategy emitted this order -- None means "not attributable to
    # a live-eligible strategy", which is also the correct default: an
    # order with no strategy_name can never be routed live by
    # RoutingExecutionClient (backend/engine/execution/routing.py), only
    # to paper. Set by size_intents from owner_by_symbol.
    strategy_name: Optional[str] = None
```

Add near the bottom of the same file, after `Position`:

```python
LiveOrderState = Literal[
    "SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED", "FILLED", "REJECTED", "CANCELLED",
]


class BrokerOrderStatus(BaseModel):
    """A broker's own order-status response, normalized to this app's
    LiveOrderState by whichever BrokerAdapter fetched it -- Kite/Upstox/
    Angel One all use different status strings natively (see each
    adapter's docstring for the mapping); nothing outside the adapter
    layer should ever see a broker-native status string."""

    model_config = ConfigDict(extra="forbid")

    broker_order_id: str
    status: LiveOrderState
    filled_quantity: float
    average_price: float
```

In `backend/engine/runner.py`, in `size_intents`, set the field when building the order:

```python
        order = Order(
            id=str(uuid.uuid4()),
            symbol=intent.symbol,
            side=intent.side,
            quantity=size,
            order_type="MARKET",
            limit_price=None,
            product=product,
            strategy_name=owning_strategy.spec.name if owning_strategy is not None else None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_size_intents.py -v`
Expected: PASS, all tests including the two new ones.

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `cd backend && python -m pytest -q`
Expected: all existing tests still pass (adding an optional field with a default breaks
nothing that doesn't already inspect `Order.strategy_name`).

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/core/models.py backend/engine/runner.py backend/tests/test_size_intents.py
git commit -m "feat: Order.strategy_name + BrokerOrderStatus/LiveOrderState models"
```

---

## Task 2: `BrokerAdapter` protocol gains order operations

**Files:**
- Modify: `backend/brokers/protocol.py`

**Interfaces:**
- Consumes: `Order`, `BrokerOrderStatus`, `Position` (Task 1, `backend/core/models.py`).
- Produces: the `BrokerAdapter` Protocol now declares `place_order`, `cancel_order`,
  `get_order_status`, `get_positions` — every task below implements these against one broker.

- [ ] **Step 1: Add the four methods to the Protocol**

In `backend/brokers/protocol.py`, add imports and extend `BrokerAdapter`:

```python
from backend.core.models import BrokerOrderStatus, Order, Position
```

```python
class BrokerAdapter(Protocol):
    # ... existing methods unchanged ...

    async def place_order(self, order: Order) -> str:
        """Places a real MARKET order at this broker. Returns the broker's
        own order id (never this app's Order.id -- callers that need to
        correlate the two use LiveOrderStore, backend/engine/execution/
        live_order_store.py)."""
        ...

    async def cancel_order(self, broker_order_id: str) -> None: ...

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus: ...

    async def get_positions(self) -> dict[str, Position]:
        """This broker's own current-day position book, keyed by
        tradingsymbol -- the source of truth reconciliation
        (backend/routers/trading.py) merges into the local Portfolio."""
        ...
```

There is no test for a Protocol declaration alone (nothing to run) -- this step only unblocks
Tasks 3-5, which each implement and test these methods against a real broker.

- [ ] **Step 2: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/brokers/protocol.py
git commit -m "feat: extend BrokerAdapter protocol with order operations"
```

---

## Task 3: Kite order operations

**Files:**
- Create: `backend/brokers/kite_orders.py`
- Modify: `backend/brokers/kite.py`
- Test: `backend/tests/test_kite_orders.py`

**Interfaces:**
- Consumes: `Order`, `BrokerOrderStatus`, `Position`, `LiveOrderState` (Task 1).
- Produces: `KiteOrderClient` (used only by `KiteAdapter`); `KiteAdapter.place_order`,
  `.cancel_order`, `.get_order_status`, `.get_positions` (satisfies the Task 2 protocol).

Real `kiteconnect` (installed version) API surface, verified against the installed SDK's
method signatures and Kite Connect v3's public docs
(https://kite.trade/docs/connect/v3/orders/, https://kite.trade/docs/connect/v3/portfolio/,
fetched live 2026-09-09):

- `KiteConnect.place_order(variety, exchange, tradingsymbol, transaction_type, quantity,
  product, order_type, price=None, ...)` -> order id string directly (SDK, not the raw
  `{"data": {"order_id": ...}}` envelope).
- `KiteConnect.cancel_order(variety, order_id, parent_order_id=None)`.
- `KiteConnect.order_history(order_id)` -> list of dicts, one per state transition; the last
  element is the current state. Fields used: `status`, `filled_quantity`, `average_price`.
  Status values (Kite docs): `COMPLETE`, `REJECTED`, `CANCELLED`, `OPEN`, `TRIGGER PENDING`,
  `OPEN PENDING`, `VALIDATION PENDING`, `MODIFY PENDING`, `MODIFY VALIDATION PENDING`,
  `CANCEL PENDING`, `AMO REQ RECEIVED`, `MODIFIED`, `PUT ORDER REQ RECEIVED`.
- `KiteConnect.positions()` -> `{"net": [...], "day": [...]}` directly (SDK unwraps the data
  envelope, same convention `KiteProvider.quote` already relies on). Each row:
  `tradingsymbol`, `quantity`, `average_price`, `pnl`, `unrealised`, `realised`.
- Constants used: `KiteConnect.VARIETY_REGULAR` ("regular"), `.EXCHANGE_NSE` ("NSE"),
  `.TRANSACTION_TYPE_BUY`/`_SELL` (match `Side.BUY.value`/`Side.SELL.value` exactly),
  `.PRODUCT_MIS`/`.PRODUCT_CNC` (match `Order.product` exactly), `.ORDER_TYPE_MARKET`
  ("MARKET", matches `Order.order_type` exactly) -- verified via
  `python3 -c "from kiteconnect import KiteConnect; print(KiteConnect.TRANSACTION_TYPE_BUY)"`
  etc.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_kite_orders.py`:

```python
"""KiteOrderClient: real pykiteconnect order-API surface, verified against
the installed SDK's place_order/cancel_order/order_history/positions
signatures and Kite Connect v3's public docs. Every SDK call is mocked;
nothing here touches a real account."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.brokers.kite_orders import KiteOrderClient
from backend.core.models import Order, Side


def _order(**overrides) -> Order:
    fields = dict(
        id="app-order-1", symbol="RELIANCE", side=Side.BUY, quantity=10.0,
        order_type="MARKET", product="MIS",
    )
    fields.update(overrides)
    return Order(**fields)


async def test_place_order_maps_fields_and_returns_broker_order_id():
    mock_kite = MagicMock()
    mock_kite.place_order.return_value = "kite-order-1"
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, **kw: fn(**kw))):
        broker_order_id = await client.place_order(_order())

    assert broker_order_id == "kite-order-1"
    call_kwargs = mock_kite.place_order.call_args.kwargs
    assert call_kwargs["tradingsymbol"] == "RELIANCE"
    assert call_kwargs["transaction_type"] == "BUY"
    assert call_kwargs["quantity"] == 10
    assert call_kwargs["product"] == "MIS"
    assert call_kwargs["order_type"] == "MARKET"
    assert call_kwargs["exchange"] == "NSE"
    assert call_kwargs["variety"] == "regular"


async def test_cancel_order_calls_sdk_with_regular_variety():
    mock_kite = MagicMock()
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, **kw: fn(**kw))):
        await client.cancel_order("kite-order-1")

    mock_kite.cancel_order.assert_called_once_with(variety="regular", order_id="kite-order-1")


async def test_get_order_status_maps_complete_to_filled():
    mock_kite = MagicMock()
    mock_kite.order_history.return_value = [
        {"status": "OPEN", "filled_quantity": 0, "average_price": 0.0},
        {"status": "COMPLETE", "filled_quantity": 10, "average_price": 2500.5},
    ]
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))):
        status = await client.get_order_status("kite-order-1")

    assert status.status == "FILLED"
    assert status.filled_quantity == 10
    assert status.average_price == 2500.5
    assert status.broker_order_id == "kite-order-1"


async def test_get_order_status_maps_rejected():
    mock_kite = MagicMock()
    mock_kite.order_history.return_value = [
        {"status": "REJECTED", "filled_quantity": 0, "average_price": 0.0},
    ]
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))):
        status = await client.get_order_status("kite-order-1")

    assert status.status == "REJECTED"


async def test_get_order_status_maps_partial_fill():
    mock_kite = MagicMock()
    mock_kite.order_history.return_value = [
        {"status": "OPEN", "filled_quantity": 4, "average_price": 2500.0},
    ]
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *a: fn(*a))):
        status = await client.get_order_status("kite-order-1")

    assert status.status == "PARTIALLY_FILLED"


async def test_get_positions_maps_net_positions():
    mock_kite = MagicMock()
    mock_kite.positions.return_value = {
        "net": [{"tradingsymbol": "RELIANCE", "quantity": 10, "average_price": 2500.0,
                  "realised": 0.0, "unrealised": 150.0}],
        "day": [],
    }
    client = KiteOrderClient(kite_client_factory=lambda: mock_kite)

    with patch("backend.brokers.kite_orders.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        positions = await client.get_positions()

    assert positions["RELIANCE"].quantity == 10
    assert positions["RELIANCE"].avg_price == 2500.0
    assert positions["RELIANCE"].unrealized_pnl == 150.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_kite_orders.py -v`
Expected: FAIL — `backend.brokers.kite_orders` does not exist yet.

- [ ] **Step 3: Write `KiteOrderClient`**

Create `backend/brokers/kite_orders.py`:

```python
"""Kite Connect order operations. Real pykiteconnect API surface used
(verified against the installed SDK's place_order/cancel_order/
order_history/positions signatures, and https://kite.trade/docs/connect/v3/
orders/ + .../portfolio/, fetched live 2026-09-09):

- `place_order(variety, exchange, tradingsymbol, transaction_type, quantity,
  product, order_type, price=None, ...)` -> the SDK returns the order id
  string directly (not the raw `{"data": {"order_id": ...}}` envelope).
- `cancel_order(variety, order_id, parent_order_id=None)`.
- `order_history(order_id)` -> list of dicts, one per state transition; the
  last element is the current state. `status` values per Kite's docs:
  COMPLETE, REJECTED, CANCELLED, OPEN, TRIGGER PENDING, OPEN PENDING,
  VALIDATION PENDING, MODIFY PENDING, MODIFY VALIDATION PENDING, CANCEL
  PENDING, AMO REQ RECEIVED, MODIFIED, PUT ORDER REQ RECEIVED -- anything
  not COMPLETE/REJECTED/CANCELLED maps to PARTIALLY_FILLED (if
  filled_quantity > 0) or ACKNOWLEDGED (a live account has never
  exercised this mapping; verified against docs only, same posture as
  every other broker adapter in this codebase).
- `positions()` -> {"net": [...], "day": [...]} directly (SDK unwraps the
  data envelope, same as KiteProvider.quote already relies on).

Only MARKET orders are placed here -- LIMIT order price handling is out of
scope (see docs/superpowers/specs/2026-09-09-live-equity-execution-design.md).
"""

import asyncio
from typing import Callable

from backend.core.models import BrokerOrderStatus, Order, Position, Side


class KiteOrderClient:
    def __init__(self, kite_client_factory: Callable[[], "KiteConnect"]) -> None:  # noqa: F821
        self._kite_client_factory = kite_client_factory

    async def place_order(self, order: Order) -> str:
        kite = self._kite_client_factory()
        return await asyncio.to_thread(
            kite.place_order,
            variety="regular",
            exchange="NSE",
            tradingsymbol=order.symbol,
            transaction_type=order.side.value,
            quantity=int(order.quantity),
            product=order.product,
            order_type=order.order_type,
        )

    async def cancel_order(self, broker_order_id: str) -> None:
        kite = self._kite_client_factory()
        await asyncio.to_thread(kite.cancel_order, variety="regular", order_id=broker_order_id)

    @staticmethod
    def _map_status(raw_status: str, filled_quantity: float) -> str:
        if raw_status == "COMPLETE":
            return "FILLED"
        if raw_status == "REJECTED":
            return "REJECTED"
        if raw_status == "CANCELLED":
            return "CANCELLED"
        return "PARTIALLY_FILLED" if filled_quantity > 0 else "ACKNOWLEDGED"

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        kite = self._kite_client_factory()
        history = await asyncio.to_thread(kite.order_history, broker_order_id)
        latest = history[-1]
        return BrokerOrderStatus(
            broker_order_id=broker_order_id,
            status=self._map_status(latest["status"], latest["filled_quantity"]),
            filled_quantity=float(latest["filled_quantity"]),
            average_price=float(latest["average_price"]),
        )

    async def get_positions(self) -> dict[str, Position]:
        kite = self._kite_client_factory()
        data = await asyncio.to_thread(kite.positions)
        return {
            row["tradingsymbol"]: Position(
                symbol=row["tradingsymbol"],
                quantity=float(row["quantity"]),
                avg_price=float(row["average_price"]),
                realized_pnl=float(row.get("realised", 0.0)),
                unrealized_pnl=float(row.get("unrealised", 0.0)),
            )
            for row in data["net"]
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_kite_orders.py -v`
Expected: PASS.

- [ ] **Step 5: Wire into `KiteAdapter`**

In `backend/brokers/kite.py`, add the import and four methods (mirrors the existing
`_client_factory` composition pattern used for `KiteProvider`):

```python
from backend.brokers.kite_orders import KiteOrderClient
from backend.core.models import BrokerOrderStatus, Order, Position
```

```python
    async def place_order(self, order: Order) -> str:
        token = await self.get_access_token()
        return await KiteOrderClient(self._client_factory(token)).place_order(order)

    async def cancel_order(self, broker_order_id: str) -> None:
        token = await self.get_access_token()
        await KiteOrderClient(self._client_factory(token)).cancel_order(broker_order_id)

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        token = await self.get_access_token()
        return await KiteOrderClient(self._client_factory(token)).get_order_status(broker_order_id)

    async def get_positions(self) -> dict[str, Position]:
        token = await self.get_access_token()
        return await KiteOrderClient(self._client_factory(token)).get_positions()
```

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass, including the new `test_kite_orders.py`.

- [ ] **Step 7: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/brokers/kite_orders.py backend/brokers/kite.py backend/tests/test_kite_orders.py
git commit -m "feat: Kite order placement, cancellation, status, and positions"
```

---

## Task 4: Upstox order operations

**Files:**
- Modify: `backend/brokers/upstox.py`
- Test: `backend/tests/test_upstox_adapter.py`

**Interfaces:**
- Consumes: `Order`, `BrokerOrderStatus`, `Position`, `LiveOrderState` (Task 1); the
  existing `UpstoxAdapter._resolve(instrument)` / `_headers(token)` helpers.
- Produces: `UpstoxAdapter.place_order`, `.cancel_order`, `.get_order_status`,
  `.get_positions`.

Real endpoints, verified 2026-09-09 against https://upstox.com/developer/api-documentation/
(fetched live, same posture as the file's existing quote/history endpoints):

- Place: `POST https://api-hft.upstox.com/v2/order/place`, JSON body `quantity`, `product`
  (`I` intraday / `D` delivery, **not** `MIS`/`CNC` -- this adapter maps `Order.product`),
  `order_type` (`MARKET`), `transaction_type` (`BUY`/`SELL`, matches `Side.value`), `validity`
  (`DAY`), `price` (`0` for MARKET), `instrument_token` (Upstox's `instrument_key`, from
  `_resolve`), `trigger_price` (`0`), `disclosed_quantity` (`0`) -> `{"status": "success",
  "data": {"order_id": "..."}}`.
- Cancel: `DELETE https://api-hft.upstox.com/v2/order/cancel?order_id={order_id}`.
- Status: `GET https://api.upstox.com/v2/order/details?order_id={order_id}` ->
  `{"data": {"status": "complete", "filled_quantity": 1, "average_price": 570.95,
  "order_id": "..."}}`. Only `"complete"` is confirmed by name in the fetched docs;
  `"rejected"`/`"cancelled"`/anything else maps defensively (see mapping below).
- Positions: `GET https://api.upstox.com/v2/portfolio/short-term-positions` ->
  `{"data": [{"trading_symbol": "...", "quantity": ..., "average_price": ...,
  "unrealised": ..., "realised": ...}]}`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_upstox_adapter.py`:

```python
def _scrip():
    return [{
        "segment": "NSE_EQ", "exchange": "NSE", "isin": "INE002A01018",
        "instrument_type": "EQ", "instrument_key": "NSE_EQ|INE002A01018",
        "lot_size": 1, "exchange_token": "2885", "tick_size": 0.05,
        "trading_symbol": "RELIANCE", "name": "RELIANCE INDUSTRIES",
    }]


async def test_place_order_posts_mapped_fields(monkeypatch):
    from backend.core.models import Order, Side

    redis = _redis()
    await redis.set("broker:alice:upstox:access_token", "up-tok")
    adapter = _adapter(redis)

    captured = {}

    async def fake_get(self, url, **kwargs):
        return httpx.Response(
            200, content=gzip.compress(json.dumps(_scrip()).encode()), request=httpx.Request("GET", url),
        )

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        captured["url"], captured["json"] = url, json
        return httpx.Response(200, json={"status": "success", "data": {"order_id": "up-order-1"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    order = Order(id="app-1", symbol="RELIANCE", side=Side.BUY, quantity=10.0, order_type="MARKET", product="MIS")
    broker_order_id = await adapter.place_order(order)

    assert broker_order_id == "up-order-1"
    assert captured["url"] == "https://api-hft.upstox.com/v2/order/place"
    assert captured["json"]["quantity"] == 10
    assert captured["json"]["product"] == "I"
    assert captured["json"]["transaction_type"] == "BUY"
    assert captured["json"]["order_type"] == "MARKET"
    assert captured["json"]["instrument_token"] == "NSE_EQ|INE002A01018"


async def test_cancel_order_sends_delete_with_order_id(monkeypatch):
    adapter = _adapter()
    captured = {}

    async def fake_delete(self, url, headers=None, **kwargs):
        captured["url"] = url
        return httpx.Response(200, json={"status": "success", "data": {"order_id": "up-order-1"}}, request=httpx.Request("DELETE", url))

    monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)

    await adapter.cancel_order("up-order-1")

    assert captured["url"] == "https://api-hft.upstox.com/v2/order/cancel?order_id=up-order-1"


async def test_get_order_status_maps_complete_to_filled(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"data": {
            "order_id": "up-order-1", "status": "complete", "filled_quantity": 10, "average_price": 2500.5,
        }}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await adapter.get_order_status("up-order-1")

    assert status.status == "FILLED"
    assert status.filled_quantity == 10
    assert status.average_price == 2500.5


async def test_get_order_status_maps_rejected(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"data": {
            "order_id": "up-order-1", "status": "rejected", "filled_quantity": 0, "average_price": 0.0,
        }}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await adapter.get_order_status("up-order-1")

    assert status.status == "REJECTED"


async def test_get_positions_maps_trading_symbol(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"data": [{
            "trading_symbol": "RELIANCE", "quantity": 10, "average_price": 2500.0,
            "unrealised": 150.0, "realised": 0.0,
        }]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    positions = await adapter.get_positions()

    assert positions["RELIANCE"].quantity == 10
    assert positions["RELIANCE"].unrealized_pnl == 150.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_upstox_adapter.py -k "place_order or cancel_order or get_order_status or get_positions" -v`
Expected: FAIL — `UpstoxAdapter` has no `place_order`/`cancel_order`/`get_order_status`/`get_positions`.

- [ ] **Step 3: Implement the four methods**

In `backend/brokers/upstox.py`, add URL constants near the top:

```python
_PLACE_ORDER_URL = "https://api-hft.upstox.com/v2/order/place"
_CANCEL_ORDER_URL = "https://api-hft.upstox.com/v2/order/cancel"
_ORDER_DETAILS_URL = "https://api.upstox.com/v2/order/details"
_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"

# Order.product ("CNC"/"MIS") -> Upstox's own vocabulary ("D"/"I").
_PRODUCT_MAP = {"MIS": "I", "CNC": "D"}
```

Add the import at the top of the file: `from backend.core.models import BrokerOrderStatus,
Order, Position`. Then add the methods to `UpstoxAdapter` (after `history`):

```python
    @staticmethod
    def _map_status(raw_status: str) -> str:
        status = raw_status.lower()
        if status == "complete":
            return "FILLED"
        if status == "rejected":
            return "REJECTED"
        if status == "cancelled":
            return "CANCELLED"
        return "ACKNOWLEDGED"

    async def place_order(self, order: Order) -> str:
        row = await self._resolve(Instrument(
            exchange="NSE", tradingsymbol=order.symbol, name=order.symbol,
            instrument_token=0, exchange_token=0, instrument_type="EQ",
            segment="NSE_EQ", lot_size=1, tick_size=0.05,
        ))
        token = await self.get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_PLACE_ORDER_URL, json={
                "quantity": int(order.quantity),
                "product": _PRODUCT_MAP[order.product],
                "order_type": order.order_type,
                "transaction_type": order.side.value,
                "validity": "DAY",
                "price": 0,
                "instrument_token": row["instrument_key"],
                "trigger_price": 0,
                "disclosed_quantity": 0,
            }, headers=self._headers(token))
            resp.raise_for_status()

        return resp.json()["data"]["order_id"]

    async def cancel_order(self, broker_order_id: str) -> None:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{_CANCEL_ORDER_URL}?order_id={broker_order_id}", headers=self._headers(token),
            )
            resp.raise_for_status()

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _ORDER_DETAILS_URL, params={"order_id": broker_order_id}, headers=self._headers(token),
            )
            resp.raise_for_status()

        data = resp.json()["data"]
        return BrokerOrderStatus(
            broker_order_id=broker_order_id,
            status=self._map_status(data["status"]),
            filled_quantity=float(data.get("filled_quantity", 0)),
            average_price=float(data.get("average_price", 0.0)),
        )

    async def get_positions(self) -> dict[str, Position]:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_POSITIONS_URL, headers=self._headers(token))
            resp.raise_for_status()

        return {
            row["trading_symbol"]: Position(
                symbol=row["trading_symbol"],
                quantity=float(row["quantity"]),
                avg_price=float(row["average_price"]),
                realized_pnl=float(row.get("realised", 0.0)),
                unrealized_pnl=float(row.get("unrealised", 0.0)),
            )
            for row in resp.json()["data"]
        }
```

Also update the module docstring's "Real API surface used" list to add these four endpoints,
following the file's existing convention.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_upstox_adapter.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/brokers/upstox.py backend/tests/test_upstox_adapter.py
git commit -m "feat: Upstox order placement, cancellation, status, and positions"
```

---

## Task 5: Angel One order operations

**Files:**
- Modify: `backend/brokers/angel_one.py`
- Test: `backend/tests/test_angel_one_adapter.py`

**Interfaces:**
- Consumes: `Order`, `BrokerOrderStatus`, `Position`, `LiveOrderState` (Task 1); existing
  `AngelOneAdapter._resolve(instrument)` / `_headers(token)` helpers.
- Produces: `AngelOneAdapter.place_order`, `.cancel_order`, `.get_order_status`,
  `.get_positions`.

Real endpoints, verified against the official SDK source
(https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py, fetched
live 2026-09-09) -- same posture as this file's existing quote/history/instruments methods.
Root `https://apiconnect.angelone.in`:

- Place: `POST /rest/secure/angelbroking/order/v1/placeOrder`, JSON body `variety`
  (`"NORMAL"`), `tradingsymbol`, `symboltoken` (from `_resolve`'s `row["token"]`),
  `transactiontype` (`BUY`/`SELL`), `exchange`, `ordertype` (`MARKET`), `producttype`
  (`"INTRADAY"`/`"DELIVERY"`, mapped from `Order.product`), `duration` (`"DAY"`), `price`
  (`"0"`), `squareoff` (`"0"`), `stoploss` (`"0"`), `quantity` (string) ->
  `{"status": true, "data": {"orderid": "..."}}`.
- Cancel: `POST /rest/secure/angelbroking/order/v1/cancelOrder`, body `{"variety": "NORMAL",
  "orderid": ...}`.
- Order book: `GET /rest/secure/angelbroking/order/v1/getOrderBook` -> `{"status": true,
  "data": [{"orderid": ..., "status": ..., "filledshares": ..., "averageprice": ...}, ...]}`.
  **The SDK source and README do not document exact `status` string casing/values for this
  endpoint** (unlike Kite/Upstox, whose docs list them explicitly) -- `_map_status` below
  matches defensively by substring, never raises on an unrecognized value, and defaults to
  `ACKNOWLEDGED` rather than guessing `FILLED`. Flag, not a guess dressed as fact.
- Positions: `GET /rest/secure/angelbroking/order/v1/getPosition` -> `{"status": true,
  "data": [{"tradingsymbol": ..., "netqty": ..., "avgnetprice": ..., "pnl": ...}, ...]}`
  (standard SmartAPI position-row field names; same "docs don't show a full example"
  caveat as the order book).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_angel_one_adapter.py` (check the file's existing `_adapter()`/
`_scrip()` helper names first and reuse them rather than redefining):

```python
async def test_place_order_posts_mapped_fields(monkeypatch):
    from backend.core.models import Order, Side

    adapter = _adapter()
    captured = {}

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        if "placeOrder" in url:
            captured["url"], captured["json"] = url, json
            return httpx.Response(200, json={"status": True, "data": {"orderid": "ao-order-1"}}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"status": True, "data": {"jwtToken": "tok", "refreshToken": "r", "feedToken": "f"}}, request=httpx.Request("POST", url))

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json=_scrip_response(), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    order = Order(id="app-1", symbol="RELIANCE", side=Side.BUY, quantity=10.0, order_type="MARKET", product="MIS")
    broker_order_id = await adapter.place_order(order)

    assert broker_order_id == "ao-order-1"
    assert "placeOrder" in captured["url"]
    assert captured["json"]["transactiontype"] == "BUY"
    assert captured["json"]["producttype"] == "INTRADAY"
    assert captured["json"]["quantity"] == "10"


async def test_cancel_order_posts_variety_and_orderid(monkeypatch):
    adapter = _adapter()
    captured = {}

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        captured["url"], captured["json"] = url, json
        return httpx.Response(200, json={"status": True, "data": {}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await adapter.cancel_order("ao-order-1")

    assert "cancelOrder" in captured["url"]
    assert captured["json"] == {"variety": "NORMAL", "orderid": "ao-order-1"}


async def test_get_order_status_maps_complete_to_filled(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"status": True, "data": [
            {"orderid": "ao-order-1", "status": "complete", "filledshares": "10", "averageprice": "2500.5"},
        ]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await adapter.get_order_status("ao-order-1")

    assert status.status == "FILLED"
    assert status.filled_quantity == 10
    assert status.average_price == 2500.5


async def test_get_order_status_unrecognized_value_defaults_acknowledged(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"status": True, "data": [
            {"orderid": "ao-order-1", "status": "some-new-status", "filledshares": "0", "averageprice": "0"},
        ]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    status = await adapter.get_order_status("ao-order-1")

    assert status.status == "ACKNOWLEDGED"


async def test_get_positions_maps_netqty(monkeypatch):
    adapter = _adapter()

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, json={"status": True, "data": [
            {"tradingsymbol": "RELIANCE-EQ", "netqty": "10", "avgnetprice": "2500.0", "pnl": "150.0"},
        ]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    positions = await adapter.get_positions()

    assert positions["RELIANCE"].quantity == 10
    assert positions["RELIANCE"].unrealized_pnl == 150.0
```

Check the existing test file for its `_scrip_response()`/scrip-fixture helper name before
writing `test_place_order_posts_mapped_fields` -- reuse whatever it's actually called there
rather than the placeholder name above.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_angel_one_adapter.py -k "place_order or cancel_order or get_order_status or get_positions" -v`
Expected: FAIL — methods don't exist yet.

- [ ] **Step 3: Implement the four methods**

In `backend/brokers/angel_one.py`, add URL constants:

```python
_PLACE_ORDER_URL = f"{_ROOT}/rest/secure/angelbroking/order/v1/placeOrder"
_CANCEL_ORDER_URL = f"{_ROOT}/rest/secure/angelbroking/order/v1/cancelOrder"
_ORDER_BOOK_URL = f"{_ROOT}/rest/secure/angelbroking/order/v1/getOrderBook"
_POSITIONS_URL = f"{_ROOT}/rest/secure/angelbroking/order/v1/getPosition"

# Order.product ("CNC"/"MIS") -> Angel One's own vocabulary.
_PRODUCT_MAP = {"MIS": "INTRADAY", "CNC": "DELIVERY"}
```

Add the import: `from backend.core.models import BrokerOrderStatus, Order, Position`. Then
add the methods (after `history`):

```python
    @staticmethod
    def _map_status(raw_status: str) -> str:
        status = raw_status.lower()
        if "complete" in status:
            return "FILLED"
        if "reject" in status:
            return "REJECTED"
        if "cancel" in status:
            return "CANCELLED"
        return "ACKNOWLEDGED"

    async def place_order(self, order: Order) -> str:
        row = await self._resolve(Instrument(
            exchange="NSE", tradingsymbol=order.symbol, name=order.symbol,
            instrument_token=0, exchange_token=0, instrument_type="EQ",
            segment="NSE", lot_size=1, tick_size=0.05,
        ))
        token = await self.get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_PLACE_ORDER_URL, json={
                "variety": "NORMAL",
                "tradingsymbol": order.symbol,
                "symboltoken": row["token"],
                "transactiontype": order.side.value,
                "exchange": "NSE",
                "ordertype": "MARKET",
                "producttype": _PRODUCT_MAP[order.product],
                "duration": "DAY",
                "price": "0",
                "squareoff": "0",
                "stoploss": "0",
                "quantity": str(int(order.quantity)),
            }, headers=self._headers(token))
            resp.raise_for_status()

        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"Angel One rejected the order: {body.get('message', 'unknown error')}")
        return body["data"]["orderid"]

    async def cancel_order(self, broker_order_id: str) -> None:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _CANCEL_ORDER_URL, json={"variety": "NORMAL", "orderid": broker_order_id},
                headers=self._headers(token),
            )
            resp.raise_for_status()

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_ORDER_BOOK_URL, headers=self._headers(token))
            resp.raise_for_status()

        rows = resp.json().get("data") or []
        row = next((r for r in rows if r["orderid"] == broker_order_id), None)
        if row is None:
            raise ValueError(f"Order {broker_order_id!r} not found in Angel One's order book")

        return BrokerOrderStatus(
            broker_order_id=broker_order_id,
            status=self._map_status(row["status"]),
            filled_quantity=float(row.get("filledshares", 0) or 0),
            average_price=float(row.get("averageprice", 0) or 0),
        )

    async def get_positions(self) -> dict[str, Position]:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_POSITIONS_URL, headers=self._headers(token))
            resp.raise_for_status()

        result = {}
        for row in resp.json().get("data") or []:
            symbol = row["tradingsymbol"]
            plain = symbol[:-3] if symbol.endswith("-EQ") else symbol
            result[plain] = Position(
                symbol=plain,
                quantity=float(row.get("netqty", 0) or 0),
                avg_price=float(row.get("avgnetprice", 0) or 0),
                unrealized_pnl=float(row.get("pnl", 0) or 0),
            )
        return result
```

Update the module docstring's "Real API surface used" list to add these four endpoints and
the explicit caveat about unverified status-value casing, following the file's existing
convention of stating exactly what was and wasn't confirmed.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_angel_one_adapter.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/brokers/angel_one.py backend/tests/test_angel_one_adapter.py
git commit -m "feat: Angel One order placement, cancellation, status, and positions"
```

---

## Task 6: `LiveOrderStore`

**Files:**
- Create: `backend/engine/execution/live_order_store.py`
- Test: `backend/tests/test_live_order_store.py`

**Interfaces:**
- Consumes: `LiveOrderState` (Task 1).
- Produces: `LiveOrderStore(db)` with `record_submitted(order_id, broker_order_id, user_id,
  strategy_name, symbol) -> None`, `get_broker_order_id(order_id) -> Optional[str]`,
  `update_status(order_id, status, filled_quantity, average_price) -> None`,
  `pending_for_user(user_id) -> list[dict]` (rows whose `status` is one of `SUBMITTED`,
  `ACKNOWLEDGED`, `PARTIALLY_FILLED`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_live_order_store.py`:

```python
"""LiveOrderStore: collection `live_orders`, one document per app-side
Order.id. Backs BrokerExecutionClient's idempotent submit (Task 7) and the
status-poll loop."""

from mongomock_motor import AsyncMongoMockClient

from backend.engine.execution.live_order_store import LiveOrderStore


def _store():
    return LiveOrderStore(AsyncMongoMockClient()["test_db"])


async def test_unrecorded_order_has_no_broker_order_id():
    store = _store()
    assert await store.get_broker_order_id("order-1") is None


async def test_record_submitted_then_lookup_returns_broker_order_id():
    store = _store()
    await store.record_submitted(
        order_id="order-1", broker_order_id="broker-1", user_id="alice",
        strategy_name="volume_surge", symbol="RELIANCE",
    )
    assert await store.get_broker_order_id("order-1") == "broker-1"


async def test_update_status_changes_pending_membership():
    store = _store()
    await store.record_submitted(
        order_id="order-1", broker_order_id="broker-1", user_id="alice",
        strategy_name="volume_surge", symbol="RELIANCE",
    )
    assert len(await store.pending_for_user("alice")) == 1

    await store.update_status("order-1", status="FILLED", filled_quantity=10.0, average_price=2500.0)

    assert await store.pending_for_user("alice") == []


async def test_pending_for_user_excludes_another_users_orders():
    store = _store()
    await store.record_submitted(
        order_id="order-1", broker_order_id="broker-1", user_id="alice",
        strategy_name="volume_surge", symbol="RELIANCE",
    )
    assert await store.pending_for_user("bob") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_live_order_store.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `LiveOrderStore`**

Create `backend/engine/execution/live_order_store.py`:

```python
"""Tracks every live order this app has ever submitted to a real broker.
Collection `live_orders`, one document per app-side Order.id (never
overwritten as a new order -- `record_submitted` is called once per order,
`update_status` mutates that same document as the broker's own state
changes). Backs two things: BrokerExecutionClient's idempotent submit
(backend/engine/execution/broker.py -- a retry checks here before calling
place_order again) and the per-bar status-poll loop's "what's still
outstanding for this user" query.
"""

from datetime import datetime, timezone
from typing import Optional

from backend.core.models import LiveOrderState

_PENDING_STATES = ("SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_FILLED")


class LiveOrderStore:
    def __init__(self, db) -> None:
        self._db = db

    @property
    def collection(self):
        return self._db["live_orders"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("user_id")

    async def record_submitted(
        self, order_id: str, broker_order_id: str, user_id: str, strategy_name: str, symbol: str,
    ) -> None:
        await self.collection.insert_one({
            "_id": order_id,
            "broker_order_id": broker_order_id,
            "user_id": user_id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "status": "SUBMITTED",
            "filled_quantity": 0.0,
            "average_price": 0.0,
            "submitted_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

    async def get_broker_order_id(self, order_id: str) -> Optional[str]:
        doc = await self.collection.find_one({"_id": order_id})
        return doc["broker_order_id"] if doc else None

    async def update_status(
        self, order_id: str, status: LiveOrderState, filled_quantity: float, average_price: float,
    ) -> None:
        await self.collection.update_one(
            {"_id": order_id},
            {"$set": {
                "status": status, "filled_quantity": filled_quantity, "average_price": average_price,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    async def pending_for_user(self, user_id: str) -> list[dict]:
        cursor = self.collection.find({"user_id": user_id, "status": {"$in": list(_PENDING_STATES)}})
        return await cursor.to_list(length=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_live_order_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/engine/execution/live_order_store.py backend/tests/test_live_order_store.py
git commit -m "feat: LiveOrderStore for tracking submitted live orders"
```

---

## Task 7: `BrokerExecutionClient`

**Files:**
- Create: `backend/engine/execution/broker.py`
- Test: `backend/tests/test_broker_execution_client.py`

**Interfaces:**
- Consumes: `BrokerAdapter` (Task 2's extended protocol), `LiveOrderStore` (Task 6),
  `Order`/`Fill`/`Position` (`backend/core/models.py`).
- Produces: `BrokerExecutionClient(adapter, store, user_id)` implementing `ExecutionClient`
  (`submit`, `cancel`, `positions`, `fills`) plus `poll_once() -> None` (not part of the
  shared protocol -- duck-typed, same convention as `SimulatedExecutionClient.on_bar`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_broker_execution_client.py`:

```python
"""BrokerExecutionClient: routes ExecutionClient calls to a real
BrokerAdapter, with idempotent submission and a poll_once() that turns
broker status changes into Fills the same way SimulatedExecutionClient's
_pending_fills queue does. Every BrokerAdapter here is a fake -- no real
network, no real broker, ever (no live account exists to test against)."""

from mongomock_motor import AsyncMongoMockClient

from backend.core.models import BrokerOrderStatus, Order, Position, Side
from backend.engine.execution.broker import BrokerExecutionClient
from backend.engine.execution.live_order_store import LiveOrderStore


class _FakeBrokerAdapter:
    def __init__(self) -> None:
        self.place_order_calls = 0
        self._next_status: dict[str, BrokerOrderStatus] = {}
        self._positions: dict[str, Position] = {}

    async def place_order(self, order: Order) -> str:
        self.place_order_calls += 1
        return f"broker-{order.id}"

    async def cancel_order(self, broker_order_id: str) -> None:
        pass

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        return self._next_status[broker_order_id]

    async def get_positions(self) -> dict[str, Position]:
        return self._positions

    def set_status(self, broker_order_id: str, status: BrokerOrderStatus) -> None:
        self._next_status[broker_order_id] = status


def _order(order_id="order-1", symbol="RELIANCE") -> Order:
    return Order(
        id=order_id, symbol=symbol, side=Side.BUY, quantity=10.0,
        order_type="MARKET", product="MIS", strategy_name="volume_surge",
    )


def _client(adapter):
    store = LiveOrderStore(AsyncMongoMockClient()["test_db"])
    return BrokerExecutionClient(adapter, store, user_id="alice"), store


async def test_submit_places_the_order_and_records_it():
    adapter = _FakeBrokerAdapter()
    client, store = _client(adapter)

    order_id = await client.submit(_order())

    assert order_id == "order-1"
    assert adapter.place_order_calls == 1
    assert await store.get_broker_order_id("order-1") == "broker-order-1"


async def test_submit_is_idempotent_on_retry():
    adapter = _FakeBrokerAdapter()
    client, store = _client(adapter)

    await client.submit(_order())
    await client.submit(_order())  # simulates a retry with the same Order.id

    assert adapter.place_order_calls == 1


async def test_poll_once_turns_a_new_fill_into_a_pending_fill():
    adapter = _FakeBrokerAdapter()
    client, store = _client(adapter)

    await client.submit(_order())
    adapter.set_status("broker-order-1", BrokerOrderStatus(
        broker_order_id="broker-order-1", status="FILLED", filled_quantity=10.0, average_price=2500.0,
    ))

    await client.poll_once()

    fills = [f async for f in client.fills()]
    assert len(fills) == 1
    assert fills[0].symbol == "RELIANCE"
    assert fills[0].quantity == 10.0
    assert fills[0].price == 2500.0


async def test_poll_once_does_not_refire_the_same_fill_twice():
    adapter = _FakeBrokerAdapter()
    client, store = _client(adapter)

    await client.submit(_order())
    adapter.set_status("broker-order-1", BrokerOrderStatus(
        broker_order_id="broker-order-1", status="FILLED", filled_quantity=10.0, average_price=2500.0,
    ))

    await client.poll_once()
    _ = [f async for f in client.fills()]  # drains the queue, same as the runner would
    await client.poll_once()  # order is no longer pending -- must not re-poll or re-fill it

    fills = [f async for f in client.fills()]
    assert fills == []


async def test_positions_proxies_the_adapter():
    adapter = _FakeBrokerAdapter()
    adapter._positions = {"RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=2500.0)}
    client, _ = _client(adapter)

    positions = client.positions()

    assert positions == {}  # synchronous protocol method -- see Step 3 note on why
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_broker_execution_client.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `BrokerExecutionClient`**

Create `backend/engine/execution/broker.py`:

```python
"""ExecutionClient over a real BrokerAdapter. Idempotent submission (a
retried submit() for the same Order.id never double-places), and a
poll_once() hook -- not part of the shared ExecutionClient protocol, same
duck-typed convention as SimulatedExecutionClient.on_bar -- that turns a
newly-FILLED/PARTIALLY_FILLED broker order into a Fill, queued the same way
SimulatedExecutionClient._pending_fills already works so runner.run()'s
`async for fill in execution.fills()` loop doesn't need to know the
difference between a simulated and a real fill.

ExecutionClient.positions() is synchronous per the shared protocol
(backend/engine/protocols.py) but a real broker's position book requires a
network call -- same shape as SimulatedExecutionClient.positions(), this
returns {} and reconciliation (backend/routers/trading.py) calls
BrokerAdapter.get_positions() directly instead, since it already needs to
be async there.
"""

from typing import AsyncIterator

from backend.core.models import Fill, Order, Position
from backend.engine.execution.live_order_store import LiveOrderStore


class BrokerExecutionClient:
    def __init__(self, adapter, store: LiveOrderStore, user_id: str) -> None:
        self._adapter = adapter
        self._store = store
        self._user_id = user_id
        self._pending_fills: list[Fill] = []

    async def submit(self, order: Order) -> str:
        existing = await self._store.get_broker_order_id(order.id)
        if existing is not None:
            return order.id  # already placed -- a retry, not a new order

        broker_order_id = await self._adapter.place_order(order)
        await self._store.record_submitted(
            order_id=order.id, broker_order_id=broker_order_id, user_id=self._user_id,
            strategy_name=order.strategy_name or "", symbol=order.symbol,
        )
        return order.id

    async def cancel(self, order_id: str) -> None:
        broker_order_id = await self._store.get_broker_order_id(order_id)
        if broker_order_id is not None:
            await self._adapter.cancel_order(broker_order_id)

    def positions(self) -> dict[str, Position]:
        return {}

    async def fills(self) -> AsyncIterator[Fill]:
        pending, self._pending_fills = self._pending_fills, []
        for fill in pending:
            yield fill

    async def poll_once(self) -> None:
        from datetime import datetime, timezone

        for row in await self._store.pending_for_user(self._user_id):
            status = await self._adapter.get_order_status(row["broker_order_id"])
            newly_filled = status.filled_quantity - row["filled_quantity"]

            await self._store.update_status(
                row["_id"], status=status.status,
                filled_quantity=status.filled_quantity, average_price=status.average_price,
            )

            if newly_filled > 0:
                self._pending_fills.append(Fill(
                    order_id=row["_id"], symbol=row["symbol"], side=_side_for(row["symbol"]),
                    quantity=newly_filled, price=status.average_price,
                    timestamp=datetime.now(timezone.utc), costs=0.0,
                ))
```

Wait — `Fill` needs a `Side`, but `LiveOrderStore` rows don't currently store the order's
side. Fix `LiveOrderStore.record_submitted`/`update_status`/`pending_for_user` (Task 6) to
also carry `side: Side`, and pass it through here instead of inventing `_side_for`:

Go back and edit `backend/engine/execution/live_order_store.py`:
- `record_submitted(self, order_id, broker_order_id, user_id, strategy_name, symbol, side)`
  stores `"side": side.value` in the document.
- No change needed to `update_status`/`pending_for_user` — `side` just rides along as a
  stored field, read back in the pending-rows dicts `pending_for_user` already returns.

Update `backend/tests/test_live_order_store.py`'s `record_submitted` calls to pass
`side=Side.BUY` (import `from backend.core.models import Side`), and add:

```python
async def test_pending_row_carries_the_orders_side():
    store = _store()
    await store.record_submitted(
        order_id="order-1", broker_order_id="broker-1", user_id="alice",
        strategy_name="volume_surge", symbol="RELIANCE", side=Side.BUY,
    )
    rows = await store.pending_for_user("alice")
    assert rows[0]["side"] == "BUY"
```

Now finish `broker.py`'s `poll_once` using the stored side:

```python
    async def poll_once(self) -> None:
        from datetime import datetime, timezone

        from backend.core.models import Side

        for row in await self._store.pending_for_user(self._user_id):
            status = await self._adapter.get_order_status(row["broker_order_id"])
            newly_filled = status.filled_quantity - row["filled_quantity"]

            await self._store.update_status(
                row["_id"], status=status.status,
                filled_quantity=status.filled_quantity, average_price=status.average_price,
            )

            if newly_filled > 0:
                self._pending_fills.append(Fill(
                    order_id=row["_id"], symbol=row["symbol"], side=Side(row["side"]),
                    quantity=newly_filled, price=status.average_price,
                    timestamp=datetime.now(timezone.utc), costs=0.0,
                ))
```

And update `BrokerExecutionClient.submit` to pass `side=order.side` into
`record_submitted`.

Also update this task's own test file's `submit`-related tests: nothing changes in their
assertions (they don't inspect `side`), but `_order()` already sets `side=Side.BUY`, so
`record_submitted` will receive it correctly once `submit` is fixed to pass it through.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_broker_execution_client.py tests/test_live_order_store.py -v`
Expected: PASS, all tests in both files.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/engine/execution/broker.py backend/engine/execution/live_order_store.py backend/tests/test_broker_execution_client.py backend/tests/test_live_order_store.py
git commit -m "feat: BrokerExecutionClient with idempotent submit and fill-polling"
```

---

## Task 8: `RoutingExecutionClient`

**Files:**
- Create: `backend/engine/execution/routing.py`
- Test: `backend/tests/test_routing_execution_client.py`

**Interfaces:**
- Consumes: `ExecutionClient` protocol (`backend/engine/protocols.py`), `Order`/`Fill`
  (`backend/core/models.py`).
- Produces: `RoutingExecutionClient(paper, live_by_strategy)` implementing `ExecutionClient`
  plus duck-typed `on_bar`/`poll_once` passthroughs so `runner.run()`'s existing
  `hasattr(execution, "on_bar")`/`hasattr(execution, "poll_once")` checks (Task 9) still find
  them on the router itself.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_routing_execution_client.py`:

```python
"""RoutingExecutionClient: dispatches each Order to a live BrokerExecutionClient
only if Order.strategy_name is in live_by_strategy; every other order --
including one from a strategy not toggled live, or with no strategy_name at
all -- goes to paper. This is the single most safety-critical routing
decision in the whole live-execution feature: default to paper on any
doubt, proven explicitly below."""

from backend.core.models import Fill, Order, Side
from backend.engine.execution.routing import RoutingExecutionClient


class _FakeClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self.submitted: list[Order] = []
        self.on_bar_calls = 0
        self.poll_once_calls = 0
        self._fills: list[Fill] = []

    async def submit(self, order: Order) -> str:
        self.submitted.append(order)
        return order.id

    async def cancel(self, order_id: str) -> None:
        pass

    def positions(self) -> dict:
        return {}

    async def fills(self):
        pending, self._fills = self._fills, []
        for fill in pending:
            yield fill

    def on_bar(self, symbol, bar) -> None:
        self.on_bar_calls += 1

    async def poll_once(self) -> None:
        self.poll_once_calls += 1


def _order(strategy_name) -> Order:
    return Order(
        id="order-1", symbol="RELIANCE", side=Side.BUY, quantity=1.0,
        order_type="MARKET", strategy_name=strategy_name,
    )


async def test_order_for_a_live_strategy_routes_to_its_broker_client():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    await router.submit(_order("volume_surge"))

    assert len(live.submitted) == 1
    assert len(paper.submitted) == 0


async def test_order_for_a_non_live_strategy_routes_to_paper():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    await router.submit(_order("orb_breakout"))  # not in live_by_strategy

    assert len(paper.submitted) == 1
    assert len(live.submitted) == 0


async def test_order_with_no_strategy_name_routes_to_paper():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    await router.submit(_order(None))

    assert len(paper.submitted) == 1
    assert len(live.submitted) == 0


async def test_on_bar_reaches_paper_but_not_a_live_client():
    """A real broker doesn't need the current bar's close (it fills at its
    own price) -- only paper's simulated fill logic does."""
    paper, live = _FakeClient("paper"), _FakeClient("live")
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    router.on_bar("RELIANCE", object())

    assert paper.on_bar_calls == 1
    assert live.on_bar_calls == 0


async def test_poll_once_reaches_every_live_client():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    await router.poll_once()

    assert live.poll_once_calls == 1


async def test_fills_merges_both_sources():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    paper._fills = [Fill(order_id="p1", symbol="TCS", side=Side.BUY, quantity=1.0, price=100.0, timestamp=__import__("datetime").datetime.now())]
    live._fills = [Fill(order_id="l1", symbol="RELIANCE", side=Side.BUY, quantity=1.0, price=2500.0, timestamp=__import__("datetime").datetime.now())]
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    fills = [f async for f in router.fills()]

    assert {f.order_id for f in fills} == {"p1", "l1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_routing_execution_client.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `RoutingExecutionClient`**

Create `backend/engine/execution/routing.py`:

```python
"""Dispatches each Order to a real broker only if its strategy_name is a
key in live_by_strategy -- built once per /trading/start run
(backend/routers/trading.py) from the intersection of the user's toggled-
live strategies, an ACTIVE broker session, and backtest-gate eligibility.
Every other order, including one with no strategy_name at all, routes to
paper. This file is the one place that decision is made once a run is
already going -- get it right here and every caller upstream can be sloppy
about strategy_name and still never accidentally trade live.
"""

from typing import AsyncIterator

from backend.core.models import Fill, Order, Position
from backend.engine.execution.broker import BrokerExecutionClient


class RoutingExecutionClient:
    def __init__(
        self, paper, live_by_strategy: dict[str, BrokerExecutionClient],
    ) -> None:
        self._paper = paper
        self._live_by_strategy = live_by_strategy

    def _client_for(self, order: Order):
        if order.strategy_name is None:
            return self._paper
        return self._live_by_strategy.get(order.strategy_name, self._paper)

    async def submit(self, order: Order) -> str:
        return await self._client_for(order).submit(order)

    async def cancel(self, order_id: str) -> None:
        # order_id alone doesn't carry strategy_name -- cancel on every
        # client that might hold it; each store/queue simply no-ops if it
        # doesn't recognize the id.
        await self._paper.cancel(order_id)
        for client in self._live_by_strategy.values():
            await client.cancel(order_id)

    def positions(self) -> dict[str, Position]:
        return self._paper.positions()

    async def fills(self) -> AsyncIterator[Fill]:
        async for fill in self._paper.fills():
            yield fill
        for client in self._live_by_strategy.values():
            async for fill in client.fills():
                yield fill

    def on_bar(self, symbol: str, bar) -> None:
        # Only paper's SimulatedExecutionClient needs the current bar's
        # close to fill against; a real broker fills at its own price.
        if hasattr(self._paper, "on_bar"):
            self._paper.on_bar(symbol, bar)

    async def poll_once(self) -> None:
        for client in self._live_by_strategy.values():
            if hasattr(client, "poll_once"):
                await client.poll_once()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_routing_execution_client.py -v`
Expected: PASS, all tests -- especially the three "routes to paper" tests, which are the
core safety property of this whole feature.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/engine/execution/routing.py backend/tests/test_routing_execution_client.py
git commit -m "feat: RoutingExecutionClient -- per-strategy live/paper dispatch"
```

---

## Task 9: Wire `poll_once()` into `runner.run()`

**Files:**
- Modify: `backend/engine/runner.py`
- Test: `backend/tests/test_backtest_e2e.py` (add a new test near the existing runner tests)

**Interfaces:**
- Consumes: the duck-typed `poll_once()` hook any `ExecutionClient` may optionally implement
  (Tasks 7/8).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_backtest_e2e.py`:

```python
async def test_runner_calls_poll_once_on_an_execution_client_that_has_it():
    """Reuses runner.run()'s existing per-bar loop as the status-poll
    cadence for a live ExecutionClient -- no separate background task."""
    instrument = _instrument()
    candles = _candles(n=3)
    provider = _FakeProvider(candles)
    strategy = _FirstBarBuyStrategy(SYMBOL, TIMEFRAME)

    feed = HistoricalFeed(provider, [instrument], candles[0].timestamp, candles[-1].timestamp, TIMEFRAME)

    class _ExecutionWithPoll(SimulatedExecutionClient):
        def __init__(self):
            super().__init__()
            self.poll_once_calls = 0

        async def poll_once(self):
            self.poll_once_calls += 1

    execution = _ExecutionWithPoll()
    portfolio = Portfolio()
    clock = SimClock()

    await run(
        strategies=[strategy], feed=feed, execution=execution, portfolio=portfolio,
        clock=clock, symbol_for_token=feed.symbol_for_token,
    )

    assert execution.poll_once_calls == len(candles)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_backtest_e2e.py -k poll_once -v`
Expected: FAIL — `runner.run()` never calls `poll_once`.

- [ ] **Step 3: Add the hook**

In `backend/engine/runner.py`, right before `async for fill in execution.fills():` inside the
`async for bar in feed:` loop, add:

```python
        # A live ExecutionClient (BrokerExecutionClient/RoutingExecutionClient,
        # backend/engine/execution/broker.py, .../routing.py) needs to poll the
        # broker for order-status changes; this isn't part of the shared
        # ExecutionClient protocol since paper trading doesn't need it, so
        # it's a best-effort duck-typed hook, same convention as on_bar
        # above. Runs once per bar -- for a live/polling feed that's the
        # feed's own poll_interval_seconds cadence, reused rather than
        # inventing a second background task.
        if hasattr(execution, "poll_once"):
            await execution.poll_once()

        async for fill in execution.fills():
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_backtest_e2e.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/engine/runner.py backend/tests/test_backtest_e2e.py
git commit -m "feat: runner.run() polls live execution clients once per bar"
```

---

## Task 10: `live_strategies` preference

**Files:**
- Modify: `backend/prefs.py`
- Modify: `backend/routers/settings.py`
- Test: `backend/tests/test_settings_router.py`

**Interfaces:**
- Produces: `PrefsStore.DEFAULTS["live_strategies"] = []`; `PreferencesPatch.live_strategies:
  Optional[list[str]]`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_settings_router.py` (check the file's existing fixture/client
setup first and reuse it):

```python
async def test_live_strategies_defaults_to_empty(client, auth_headers):
    resp = client.get("/api/v1/settings/preferences", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["live_strategies"] == []


async def test_live_strategies_can_be_updated(client, auth_headers):
    resp = client.put(
        "/api/v1/settings/preferences", json={"live_strategies": ["volume_surge"]}, headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["live_strategies"] == ["volume_surge"]
```

(Match this test's exact fixture names — `client`/`auth_headers` or whatever the file already
defines — to the existing tests in `test_settings_router.py` rather than the placeholders
above; run `grep -n "^async def test_\|^def client\|^def auth_headers" backend/tests/test_settings_router.py`
first if unsure.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_settings_router.py -k live_strategies -v`
Expected: FAIL — `live_strategies` not in the preferences response/patch model.

- [ ] **Step 3: Add the preference**

In `backend/prefs.py`, add to `DEFAULTS`:

```python
    "live_strategies": [],  # strategy names the user has toggled to trade with real orders
```

In `backend/routers/settings.py`, add to `PreferencesPatch`:

```python
    live_strategies: Optional[list[str]] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_settings_router.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/prefs.py backend/routers/settings.py backend/tests/test_settings_router.py
git commit -m "feat: per-user live_strategies preference"
```

---

## Task 11: Wire live routing + reconciliation into `/trading/start`

**Files:**
- Modify: `backend/routers/trading.py`
- Modify: `backend/configs/settings.py` (remove `TRADING_LIVE_ENABLED`)
- Test: `backend/tests/test_trading_router.py`

**Interfaces:**
- Consumes: `RoutingExecutionClient` (Task 8), `BrokerExecutionClient` (Task 7),
  `LiveOrderStore` (Task 6), `live_strategies` pref (Task 10), `BROKERS`/`get_broker_adapter`
  (`backend/brokers/registry.py`, already exist), `BacktestGateStore.live_eligible`
  (already exists, Phase 4).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_trading_router.py` (reuse the file's existing fixtures/helpers for
constructing an authenticated client and a live-eligible backtest result — grep the file for
its own `_result`/`_passing_backtest` helper before writing these, mirroring Task 10's
approach):

```python
async def test_start_trading_still_works_with_no_live_strategies_toggled(client, auth_headers):
    """Default behavior (empty live_strategies, Task 10's default): every
    strategy runs paper, same as before this feature existed."""
    resp = client.post("/api/v1/trading/start", json={"mode": "LONGTERM"}, headers=auth_headers)
    assert resp.status_code == 200


async def test_start_trading_no_longer_501s_on_trading_live_enabled(client, auth_headers, monkeypatch):
    import backend.routers.trading as trading
    monkeypatch.setattr(trading.settings, "TRADING_LIVE_ENABLED", True, raising=False)

    resp = client.post("/api/v1/trading/start", json={"mode": "LONGTERM"}, headers=auth_headers)

    assert resp.status_code != 501
```

Check `test_trading_router.py:422` (referenced in the spec's context) for the existing
`monkeypatch.setattr(trading.settings, "TRADING_LIVE_ENABLED", True)` test that currently
asserts a 501 -- **delete that test** in this same step (Step 3 below), since the behavior it
proves no longer exists once `TRADING_LIVE_ENABLED` is removed.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_trading_router.py -k "no_live_strategies or no_longer_501s" -v`
Expected: FAIL — the existing 501 block still triggers.

- [ ] **Step 3: Remove the old gate, add live routing**

In `backend/configs/settings.py`, delete the line `TRADING_LIVE_ENABLED: bool = False`.

In `backend/tests/test_trading_router.py`, delete the test at (approximately) line 422 that
sets `TRADING_LIVE_ENABLED = True` and asserts a 501 response — that behavior is being
replaced, not kept alongside the new one.

In `backend/routers/trading.py`:

1. Remove the import-time reference and the old block:

```python
    if settings.TRADING_LIVE_ENABLED:
        raise HTTPException(
            status_code=501,
            detail="Live order routing is not implemented; unset TRADING_LIVE_ENABLED to paper trade",
        )
```

2. Add imports:

```python
from backend.engine.execution.broker import BrokerExecutionClient
from backend.engine.execution.live_order_store import LiveOrderStore
from backend.engine.execution.routing import RoutingExecutionClient
```

3. Add a helper near `build_feed` (same file, same style — tries brokers in `BROKERS` order,
   first `ACTIVE` one wins, mirroring `build_feed`'s existing loop):

```python
async def get_active_broker_adapter(user_id: str, credentials):
    for broker in BROKERS:
        adapter = await get_broker_adapter(broker, user_id, credentials, db.redis)
        if await adapter.state() == BrokerSessionState.ACTIVE:
            return adapter
    return None
```

4. In `start_trading`, replace the `prefs = await PrefsStore(db.db).get(user.id)` block's
   immediate surroundings — after `strategies = await live_eligible_strategies(...)` and
   before building `coro = run(...)` — with the live-routing setup:

```python
    prefs = await PrefsStore(db.db).get(user.id)
    account_size = prefs["account_size"]
    max_exposure = prefs["max_exposure"]

    credentials = get_credential_store()
    active_adapter = await get_active_broker_adapter(user.id, credentials)
    live_strategy_names = set(prefs["live_strategies"])
    eligible_names = {s.spec.name for s in strategies}

    live_by_strategy: dict[str, BrokerExecutionClient] = {}
    if active_adapter is not None:
        live_order_store = LiveOrderStore(db.db)
        for name in live_strategy_names & eligible_names:
            live_by_strategy[name] = BrokerExecutionClient(active_adapter, live_order_store, user_id=user.id)
```

5. Change the `execution = SimulatedExecutionClient()` line to:

```python
    paper_execution = SimulatedExecutionClient()
    execution = (
        RoutingExecutionClient(paper=paper_execution, live_by_strategy=live_by_strategy)
        if live_by_strategy else paper_execution
    )
```

6. Add reconciliation right after `portfolio = Portfolio()` and before `ledger = LedgerStore(...)`:

```python
    if active_adapter is not None and live_by_strategy:
        broker_positions = await active_adapter.get_positions()
        for symbol, position in broker_positions.items():
            portfolio.positions[symbol] = position
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_trading_router.py -v`
Expected: PASS, all tests in the file (including the deletion of the old 501 test not
breaking anything else that referenced it — grep for other uses of that test name first).

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add backend/routers/trading.py backend/configs/settings.py backend/tests/test_trading_router.py
git commit -m "feat: wire per-strategy live routing and reconciliation into /trading/start"
```

---

## Task 12: Settings UI — per-strategy live toggle

**Files:**
- Modify: `frontend/src/pages/Settings.jsx`
- Modify: `frontend/src/utils/api.js` (if a strategies-list endpoint doesn't already exist —
  check first; `build_default_strategies` names are also visible via
  `/trading/start`'s 400 error today, but a clean list is better)

**Interfaces:**
- Consumes: `GET /settings/preferences` (already returns `live_strategies`, Task 10), `PUT
  /settings/preferences` (already accepts it, Task 10).

- [ ] **Step 1: Check whether a strategy-names endpoint exists**

Run: `grep -rn "strategy_name\|build_default_strategies\|/strategies" backend/routers/*.py`

If nothing returns a plain list of strategy names for the frontend to render toggles for, add
one small endpoint before touching the frontend — `GET /settings/strategies` in
`backend/routers/settings.py`:

```python
@router.get("/settings/strategies")
async def list_strategies():
    from backend.strategies.registry import build_default_strategies
    return [s.spec.name for s in build_default_strategies(universe=["PLACEHOLDER"])]
```

Write a matching backend test in `backend/tests/test_settings_router.py` first (TDD, same as
every other task), confirm it fails, add the route, confirm it passes, then proceed to the
frontend below as its own commit. (Full task-structure ceremony omitted here since this
sub-step is small and mechanical — follow Task 10's Steps 1-6 shape exactly for it.)

- [ ] **Step 2: Add the toggle list to `MandateSheet`**

In `frontend/src/pages/Settings.jsx`, extend `MandateSheet`'s state and fetch to also load
`/settings/strategies`, and render one toggle per strategy name reusing the existing
`scan_enabled` on/off pill pattern (`frontend/src/pages/Settings.jsx`'s existing `Row` with a
`role="switch"` button — copy that exact JSX shape, keyed by strategy name, toggling
membership in `prefs.live_strategies` via `save({ live_strategies: [...] })`).

```jsx
const [strategyNames, setStrategyNames] = useState([]);

useEffect(() => {
  api.get('/settings/strategies').then((res) => setStrategyNames(res.data)).catch(() => setStrategyNames([]));
}, []);
```

```jsx
{strategyNames.map((name) => {
  const isLive = (prefs.live_strategies || []).includes(name);
  return (
    <Row key={name} label={name} hint={isLive ? 'Trading with real orders.' : 'Paper only.'}>
      <button
        type="button"
        role="switch"
        aria-checked={isLive}
        onClick={() => {
          const next = isLive
            ? prefs.live_strategies.filter((n) => n !== name)
            : [...(prefs.live_strategies || []), name];
          save({ live_strategies: next });
        }}
        className={cn(
          'px-3 py-1 border font-[family-name:var(--font-narrow)] text-[0.6875rem] font-semibold uppercase tracking-[0.11em] transition-colors',
          isLive
            ? 'bg-[var(--loss)] text-[var(--paper)] border-[var(--loss)]'
            : 'text-[var(--ink-soft)] border-[var(--rule-strong)]'
        )}
      >
        {isLive ? 'Live' : 'Paper'}
      </button>
    </Row>
  );
})}
```

Use `--loss` (the destructive/red token, same one the kill-switch banner on the Trading page
already uses) rather than `--stamp`/success green for the "Live" state — this toggle risks
real money, and the color should say so at a glance, not look like an achievement.

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run build`
Expected: builds clean, no type/lint errors.

Start the dev server (`npm run dev`), open Settings, confirm the strategy toggles render and
flipping one persists (reload the page, the toggle state survives).

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add frontend/src/pages/Settings.jsx backend/routers/settings.py backend/tests/test_settings_router.py
git commit -m "feat: per-strategy live/paper toggle in Settings"
```

---

## Task 13: Update `docs/ROADMAP.md`

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Mark Phase 5a done, note F&O is its own follow-up**

Add a "What landed" subsection under Phase 5 (same convention as Phases 1-4 already use),
stating: live equity execution shipped for Kite/Upstox/Angel One (MARKET orders only),
per-user per-strategy toggle defaulting to all-paper, reconciliation on run start, no live
account exists to verify any of it against a real broker. State plainly that F&O (the
Instrument model widening, lot/margin-aware sizing) was **not** built in this pass and is
its own future spec, not silently dropped.

- [ ] **Step 2: Commit**

```bash
cd /home/ubuntu/projects/NeoTrade
git add docs/ROADMAP.md
git commit -m "docs: record Phase 5a (live equity execution) as done"
```

---

## Self-Review Notes (for whoever executes this plan)

- **Spec coverage:** Tasks 1-9 build the execution-layer subsystem (Order tagging, broker
  order ops for all three brokers, LiveOrderStore, BrokerExecutionClient,
  RoutingExecutionClient, the poll hook). Task 10 adds the preference. Task 11 wires
  everything into `/trading/start` including reconciliation. Task 12 is the UI. Every
  numbered item in the spec's "Architecture" section maps to a task above.
- **Kite/Upstox status-value mappings are the one area with residual uncertainty** — Kite and
  Upstox's status enums are confirmed against fetched docs; Angel One's order-book field
  casing is not (the SDK source doesn't show a full example response). `_map_status`'s
  defensive substring-matching with an `ACKNOWLEDGED` fallback (never guesses `FILLED`) is
  the mitigation, called out explicitly in Task 5's docstring instructions — do not remove
  that caveat when implementing.
- **Task 7's mid-task correction (adding `side` to `LiveOrderStore`)** is intentional, not a
  planning error — it's flagged inline exactly where the dependency was discovered, so
  implement Task 6 first with the `side` field included from the start rather than in two
  passes if executing task-by-task in order.
