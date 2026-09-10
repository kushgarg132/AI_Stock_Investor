"""RoutingExecutionClient: dispatches each Order to a live BrokerExecutionClient
only if Order.strategy_name is in live_by_strategy; every other order --
including one from a strategy not toggled live, or with no strategy_name at
all -- goes to paper. This is the single most safety-critical routing
decision in the whole live-execution feature: default to paper on any
doubt, proven explicitly below."""

from backend.core.models import Fill, Order, Position, Side
from backend.engine.execution.routing import RoutingExecutionClient


class _FakeClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self.submitted: list[Order] = []
        self.on_bar_calls = 0
        self.poll_once_calls = 0
        self._fills: list[Fill] = []
        self._positions: dict[str, Position] = {}

    async def submit(self, order: Order) -> str:
        self.submitted.append(order)
        return order.id

    async def cancel(self, order_id: str) -> None:
        pass

    def positions(self) -> dict:
        return self._positions

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


async def test_positions_merges_both_sources():
    paper, live = _FakeClient("paper"), _FakeClient("live")
    paper._positions = {"TCS": Position(symbol="TCS", quantity=1.0, avg_price=100.0)}
    live._positions = {"RELIANCE": Position(symbol="RELIANCE", quantity=1.0, avg_price=2500.0)}
    router = RoutingExecutionClient(paper=paper, live_by_strategy={"volume_surge": live})

    positions = router.positions()

    assert set(positions) == {"TCS", "RELIANCE"}
