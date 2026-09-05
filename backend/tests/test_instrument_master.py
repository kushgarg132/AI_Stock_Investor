"""CRUD tests for InstrumentMaster against an in-memory Mongo (mongomock_motor's
AsyncMongoMockClient), which mimics motor's async API closely enough that
InstrumentMaster needs no test-only branching."""

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.instruments.loader import SeedFileSource, refresh_instruments
from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument


@pytest.fixture
async def master():
    client = AsyncMongoMockClient()
    m = InstrumentMaster(client["test_db"])
    await m.ensure_indexes()
    return m


def _make_instrument(**overrides) -> Instrument:
    defaults = dict(
        exchange="NSE",
        tradingsymbol="RELIANCE",
        name="Reliance Industries Ltd",
        instrument_token=1,
        exchange_token=1,
        instrument_type="EQ",
        segment="NSE",
        lot_size=1,
        tick_size=0.05,
    )
    defaults.update(overrides)
    return Instrument(**defaults)


async def test_upsert_and_get(master):
    inst = _make_instrument()
    count = await master.upsert_many([inst])
    assert count == 1

    fetched = await master.get("NSE", "RELIANCE")
    assert fetched is not None
    assert fetched.name == "Reliance Industries Ltd"
    assert fetched.instrument_token == 1


async def test_get_is_case_insensitive(master):
    await master.upsert_many([_make_instrument()])
    assert (await master.get("NSE", "reliance")) is not None
    assert (await master.get("NSE", "RELIANCE")) is not None


async def test_get_by_token(master):
    await master.upsert_many([_make_instrument(instrument_token=42)])
    fetched = await master.get_by_token(42)
    assert fetched is not None
    assert fetched.tradingsymbol == "RELIANCE"

    assert (await master.get_by_token(999)) is None


async def test_upsert_many_idempotent(master):
    inst = _make_instrument()
    first = await master.upsert_many([inst])
    second = await master.upsert_many([inst])
    assert first == 1
    assert second == 0  # re-running with identical data is a no-op diff


async def test_search_ranks_exact_match_first(master):
    await master.upsert_many([
        _make_instrument(tradingsymbol="TCS", name="Tata Consultancy Services Ltd", instrument_token=1),
        _make_instrument(tradingsymbol="TATASTEEL", name="Tata Steel Ltd", instrument_token=2),
        _make_instrument(tradingsymbol="TATAMOTORS", name="Tata Motors Ltd", instrument_token=3),
    ])

    results = await master.search("TATASTEEL", limit=10)
    assert results[0].tradingsymbol == "TATASTEEL"

    # Fuzzy: substring match on name should still surface all three Tata entries.
    fuzzy = await master.search("Tata", limit=10)
    assert {r.tradingsymbol for r in fuzzy} == {"TCS", "TATASTEEL", "TATAMOTORS"}


async def test_search_no_match_returns_empty(master):
    await master.upsert_many([_make_instrument()])
    assert await master.search("NOSUCHSYMBOL", limit=10) == []


async def test_seed_file_loads_into_master(master):
    count = await refresh_instruments(SeedFileSource(), master)
    assert count > 0

    reliance = await master.get("NSE", "RELIANCE")
    assert reliance is not None
    assert reliance.exchange == "NSE"
    assert reliance.instrument_type == "EQ"

    # Idempotent re-run.
    assert await refresh_instruments(SeedFileSource(), master) == 0
