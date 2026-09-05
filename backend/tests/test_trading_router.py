"""backend/routers/trading.py:
- start_background_run/stop_background_run: the actual asyncio.Task
  bookkeeping /trading/start and /trading/stop rely on -- proven directly
  against a feed that would otherwise run forever, with a timeout so a
  regression here fails fast instead of hanging the test suite.
- GET /trading/positions, /trading/fills, /trading/equity: route-level via
  FastAPI TestClient against a seeded LedgerStore (mongomock_motor).
- POST /trading/start + /trading/stop: full route round-trip with
  InstrumentMaster/YFinanceProvider/db monkeypatched to fakes, proving the
  request returns immediately and stop actually cancels the engine loop.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from backend.core.models import Fill, Position, Side
from backend.engine.persistence import LedgerStore
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.routers import trading


# ---------------------------------------------------------------------------
# start_background_run / stop_background_run
# ---------------------------------------------------------------------------

async def _forever() -> None:
    """Never returns on its own -- like the engine loop against a live
    feed -- so cancellation is the only way it ends."""
    while True:
        await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_start_returns_immediately_and_is_tracked():
    run_id = trading.start_background_run(_forever())
    try:
        assert run_id in trading._RUNS
    finally:
        await asyncio.wait_for(trading.stop_background_run(run_id), timeout=2.0)


@pytest.mark.asyncio
async def test_stop_actually_cancels_the_background_task():
    run_id = trading.start_background_run(_forever())
    stopped = await asyncio.wait_for(trading.stop_background_run(run_id), timeout=2.0)
    assert stopped is True
    assert run_id not in trading._RUNS


@pytest.mark.asyncio
async def test_stop_unknown_run_id_returns_false():
    assert await trading.stop_background_run("no-such-run") is False


# ---------------------------------------------------------------------------
# GET routes against a seeded LedgerStore
# ---------------------------------------------------------------------------

@pytest.fixture
def ledger():
    client = AsyncMongoMockClient()
    return LedgerStore(client["test_db"])


@pytest.fixture
def client(ledger):
    app = FastAPI()
    app.include_router(trading.router, prefix="/api/v1")
    app.dependency_overrides[trading.get_ledger_store] = lambda: ledger
    return TestClient(app)


def test_get_positions_returns_open_positions(client, ledger):
    asyncio.run(ledger.snapshot_positions({
        "RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=2500.0),
        "TCS": Position(symbol="TCS", quantity=0.0, avg_price=0.0),
    }))

    resp = client.get("/api/v1/trading/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"RELIANCE"}
    assert body["RELIANCE"]["quantity"] == 10.0


def test_get_fills_optionally_filters_by_symbol(client, ledger):
    asyncio.run(ledger.record_fill(Fill(
        order_id="o1", symbol="RELIANCE", side=Side.BUY, quantity=10.0,
        price=2500.0, timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), costs=12.5,
    )))
    asyncio.run(ledger.record_fill(Fill(
        order_id="o2", symbol="TCS", side=Side.BUY, quantity=5.0,
        price=3500.0, timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), costs=8.0,
    )))

    resp = client.get("/api/v1/trading/fills", params={"symbol": "RELIANCE"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["symbol"] == "RELIANCE"

    resp_all = client.get("/api/v1/trading/fills")
    assert len(resp_all.json()) == 2


def test_get_equity_reports_realized_pnl_from_open_positions(client, ledger):
    asyncio.run(ledger.snapshot_positions({
        "RELIANCE": Position(symbol="RELIANCE", quantity=10.0, avg_price=2500.0, realized_pnl=500.0),
    }))

    resp = client.get("/api/v1/trading/equity")
    assert resp.status_code == 200
    assert resp.json()["equity"] == 500.0  # no live mark price -> zero unrealized movement


# ---------------------------------------------------------------------------
# POST /trading/start + /trading/stop, full route round-trip
# ---------------------------------------------------------------------------

class _FakeMaster:
    def __init__(self, _db) -> None:
        pass

    async def get(self, exchange: str, tradingsymbol: str):
        return Instrument(
            exchange=exchange, tradingsymbol=tradingsymbol, name=tradingsymbol,
            instrument_token=hash(tradingsymbol) % 100000, exchange_token=1,
            instrument_type="EQ", segment="NSE", lot_size=1, tick_size=0.05,
        )


class _ForeverQuoteProvider:
    """Never-ending MarketDataProvider stand-in -- PollingLiveFeed's own
    while-True loop already runs forever; this just answers quote() fast so
    the test doesn't wait on a real poll_interval."""

    async def quote(self, instrument):
        return {"last_price": 100.0}

    async def history(self, instrument, interval, period):
        raise NotImplementedError


class _FakeDb:
    # A real (mongomock) database so LedgerStore(db.db) can construct its
    # collections; this test never queries them, just proves start/stop.
    db = AsyncMongoMockClient()["test_db"]
    redis = None


# ---------------------------------------------------------------------------
# GET /trading/instruments (wraps InstrumentMaster.search)
# ---------------------------------------------------------------------------

@pytest.fixture
def instruments_client(monkeypatch):
    fake_db = AsyncMongoMockClient()["test_db"]
    monkeypatch.setattr(trading, "db", type("_Db", (), {"db": fake_db})())

    async def _seed():
        master = InstrumentMaster(fake_db)
        await master.upsert_many([
            Instrument(
                exchange="NSE", tradingsymbol="RELIANCE", name="Reliance Industries",
                instrument_token=1, exchange_token=1, instrument_type="EQ",
                segment="NSE", lot_size=1, tick_size=0.05,
            ),
            Instrument(
                exchange="NSE", tradingsymbol="TCS", name="Tata Consultancy Services",
                instrument_token=2, exchange_token=2, instrument_type="EQ",
                segment="NSE", lot_size=1, tick_size=0.05,
            ),
        ])
    asyncio.run(_seed())

    app = FastAPI()
    app.include_router(trading.router, prefix="/api/v1")
    return TestClient(app)


def test_search_instruments_returns_matches(instruments_client):
    resp = instruments_client.get("/api/v1/trading/instruments", params={"q": "RELI"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["tradingsymbol"] == "RELIANCE"


def test_search_instruments_no_matches_returns_empty_list(instruments_client):
    resp = instruments_client.get("/api/v1/trading/instruments", params={"q": "NOSUCHSYMBOL"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_start_then_stop_round_trip(monkeypatch):
    monkeypatch.setattr(trading, "InstrumentMaster", _FakeMaster)
    monkeypatch.setattr(trading, "YFinanceProvider", _ForeverQuoteProvider)
    monkeypatch.setattr(trading, "db", _FakeDb)

    app = FastAPI()
    app.include_router(trading.router, prefix="/api/v1")

    with TestClient(app) as test_client:
        resp = test_client.post("/api/v1/trading/start", json={
            "mode": "LONGTERM", "universe": ["RELIANCE"], "poll_interval_seconds": 0.01,
        })
        assert resp.status_code == 200  # returns immediately, doesn't block on the loop
        run_id = resp.json()["run_id"]
        assert run_id in trading._RUNS

        stop_resp = test_client.post("/api/v1/trading/stop", json={"run_id": run_id})
        assert stop_resp.status_code == 200
        assert stop_resp.json()["stopped"] is True
        assert run_id not in trading._RUNS
