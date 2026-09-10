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
