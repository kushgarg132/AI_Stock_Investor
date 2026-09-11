from datetime import date, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.options import resolver


def test_is_fo_eligible():
    assert resolver.is_fo_eligible("RELIANCE") is True
    assert resolver.is_fo_eligible("SOME-SMALLCAP-NOT-IN-TABLE") is False


def test_next_monthly_expiry_is_last_thursday_of_month():
    # December 2024: last Thursday is the 26th.
    assert resolver.next_monthly_expiry(date(2024, 12, 1)) == date(2024, 12, 26)


def test_next_monthly_expiry_rolls_forward_when_too_close():
    # Dec 24 2024 is 2 days from the 26th -- inside the 5-day floor, rolls
    # to January 2025's last Thursday (the 30th).
    assert resolver.next_monthly_expiry(date(2024, 12, 24)) == date(2025, 1, 30)


def test_next_monthly_expiry_rolls_forward_when_already_past():
    assert resolver.next_monthly_expiry(date(2024, 12, 27)) == date(2025, 1, 30)


def test_nearest_strike_rounds_to_symbols_interval():
    # RELIANCE interval 20.0, 5% OTM below a spot of 2900 -> raw 2755, nearest
    # multiple of 20 is 2760.
    assert resolver.nearest_strike("RELIANCE", spot=2900.0, otm_pct=0.05) == 2760.0


def test_format_tradingsymbol_matches_nse_convention():
    assert resolver.format_tradingsymbol("RELIANCE", date(2024, 12, 26), 2800.0, "PE") == "RELIANCE24DEC2800PE"


def test_parse_underlying_inverts_format_tradingsymbol():
    symbol = resolver.format_tradingsymbol("RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert resolver.parse_underlying(symbol, date(2024, 12, 26), 2800.0, "PE") == "RELIANCE"


@pytest.fixture
def master():
    return InstrumentMaster(AsyncMongoMockClient()["test_db"])


@pytest.mark.asyncio
async def test_resolve_contract_finds_a_synced_nfo_row(master):
    await master.upsert_many([Instrument(
        exchange="NFO", tradingsymbol="RELIANCE24DEC2800PE", name="RELIANCE",
        instrument_token=1, exchange_token=1, instrument_type="PE", segment="NFO-OPT",
        lot_size=250, tick_size=0.05, expiry=datetime(2024, 12, 26), strike=2800.0,
    )])
    found = await resolver.resolve_contract(master, "RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert found is not None
    assert found.lot_size == 250


@pytest.mark.asyncio
async def test_resolve_contract_returns_none_when_not_synced(master):
    found = await resolver.resolve_contract(master, "RELIANCE", date(2024, 12, 26), 2800.0, "PE")
    assert found is None
