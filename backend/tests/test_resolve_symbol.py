"""Tests for the deterministic instrument resolver (backend.instruments.resolve).

Exact tradingsymbol match must win immediately with no LLM call. Ambiguous
fuzzy matches may consult the LLM, but only to choose among the returned
candidates -- an answer outside the candidate list, or zero candidates, must
raise SymbolNotFoundError rather than fabricate a symbol.
"""

from unittest.mock import AsyncMock, patch

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument
from backend.instruments.resolve import SymbolNotFoundError, resolve_symbol


@pytest.fixture
async def master():
    client = AsyncMongoMockClient()
    m = InstrumentMaster(client["test_db"])
    await m.ensure_indexes()
    await m.upsert_many([
        Instrument(
            exchange="NSE", tradingsymbol="RELIANCE", name="Reliance Industries Ltd",
            instrument_token=1, exchange_token=1, instrument_type="EQ", segment="NSE",
            lot_size=1, tick_size=0.05,
        ),
        Instrument(
            exchange="NSE", tradingsymbol="TCS", name="Tata Consultancy Services Ltd",
            instrument_token=2, exchange_token=2, instrument_type="EQ", segment="NSE",
            lot_size=1, tick_size=0.05,
        ),
        Instrument(
            exchange="NSE", tradingsymbol="TATASTEEL", name="Tata Steel Ltd",
            instrument_token=3, exchange_token=3, instrument_type="EQ", segment="NSE",
            lot_size=1, tick_size=0.05,
        ),
        Instrument(
            exchange="NSE", tradingsymbol="TATAMOTORS", name="Tata Motors Ltd",
            instrument_token=4, exchange_token=4, instrument_type="EQ", segment="NSE",
            lot_size=1, tick_size=0.05,
        ),
    ])
    return m


async def test_exact_match_no_llm_call(master):
    with patch("backend.instruments.resolve.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
        result = await resolve_symbol("RELIANCE", master)
        assert result.tradingsymbol == "RELIANCE"
        mock_llm.assert_not_called()


async def test_exact_match_is_case_insensitive(master):
    result = await resolve_symbol("reliance", master)
    assert result.tradingsymbol == "RELIANCE"


async def test_ambiguous_match_resolved_by_llm(master):
    with patch("backend.instruments.resolve.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "TATASTEEL"
        result = await resolve_symbol("Tata", master)
        assert result.tradingsymbol == "TATASTEEL"
        mock_llm.assert_called_once()


async def test_llm_answer_outside_candidates_raises(master):
    with patch("backend.instruments.resolve.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "AAPL"  # not among the candidates -- must not be trusted
        with pytest.raises(SymbolNotFoundError):
            await resolve_symbol("Tata", master)


async def test_unknown_symbol_raises_without_llm_call(master):
    with patch("backend.instruments.resolve.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
        with pytest.raises(SymbolNotFoundError):
            await resolve_symbol("NOTAREALCOMPANY", master)
        mock_llm.assert_not_called()  # zero candidates short-circuits, cheaper and deterministic
