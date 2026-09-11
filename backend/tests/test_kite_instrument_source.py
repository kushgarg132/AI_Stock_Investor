"""KiteInstrumentSource.fetch: field-mapping correctness against a canned
mock of `KiteConnect.instruments("NSE")`'s real return shape (a list of
dicts, `exchange_token` left as a string by the SDK -- see kite_source.py's
module docstring)."""

from unittest.mock import MagicMock

from backend.instruments.kite_source import KiteInstrumentSource


def _canned_kite_instruments_row(**overrides) -> dict:
    row = {
        "instrument_token": 128031748,
        "exchange_token": "500124",  # NOT cast to int by the SDK
        "tradingsymbol": "RELIANCE",
        "name": "RELIANCE INDUSTRIES",
        "last_price": 2456.75,
        "expiry": "",
        "strike": 0.0,
        "tick_size": 0.05,
        "lot_size": 1,
        "instrument_type": "EQ",
        "segment": "NSE",
        "exchange": "NSE",
    }
    row.update(overrides)
    return row


async def test_fetch_maps_kite_rows_to_instruments():
    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [_canned_kite_instruments_row()]
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite)

    instruments = await source.fetch()

    mock_kite.instruments.assert_called_once_with("NSE")
    assert len(instruments) == 1
    inst = instruments[0]
    assert inst.exchange == "NSE"
    assert inst.tradingsymbol == "RELIANCE"
    assert inst.name == "RELIANCE INDUSTRIES"
    assert inst.instrument_token == 128031748
    assert inst.exchange_token == 500124  # cast from the SDK's string
    assert isinstance(inst.exchange_token, int)
    assert inst.instrument_type == "EQ"
    assert inst.segment == "NSE"
    assert inst.lot_size == 1
    assert inst.tick_size == 0.05
    assert inst.isin is None  # Kite's dump has no ISIN column


async def test_fetch_pulls_every_configured_exchange():
    mock_kite = MagicMock()
    mock_kite.instruments.side_effect = lambda exchange: [
        _canned_kite_instruments_row(tradingsymbol=f"SYM-{exchange}", exchange=exchange)
    ]
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite, exchanges=("NSE", "BSE"))

    instruments = await source.fetch()

    assert mock_kite.instruments.call_args_list == [(("NSE",),), (("BSE",),)]
    assert [inst.tradingsymbol for inst in instruments] == ["SYM-NSE", "SYM-BSE"]
    assert [inst.exchange for inst in instruments] == ["NSE", "BSE"]


async def test_fetch_maps_multiple_rows():
    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [
        _canned_kite_instruments_row(tradingsymbol="RELIANCE", instrument_token=1),
        _canned_kite_instruments_row(tradingsymbol="TCS", instrument_token=2, exchange_token="11536"),
    ]
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite)

    instruments = await source.fetch()

    assert [inst.tradingsymbol for inst in instruments] == ["RELIANCE", "TCS"]
    assert instruments[1].exchange_token == 11536


async def test_fetch_maps_nfo_option_rows_with_expiry_and_strike():
    from datetime import date, datetime

    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [_canned_kite_instruments_row(
        tradingsymbol="RELIANCE24DEC2800PE", exchange="NFO", segment="NFO-OPT",
        instrument_type="PE", lot_size=250, strike=2800.0, expiry=date(2024, 12, 26),
    )]
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite, exchanges=("NFO",))

    instruments = await source.fetch()

    assert len(instruments) == 1
    inst = instruments[0]
    assert inst.expiry == datetime(2024, 12, 26)
    assert inst.strike == 2800.0
    assert inst.instrument_type == "PE"


async def test_fetch_maps_equity_rows_with_no_expiry_or_strike():
    mock_kite = MagicMock()
    mock_kite.instruments.return_value = [_canned_kite_instruments_row()]  # expiry="", strike=0.0
    source = KiteInstrumentSource(kite_client_factory=lambda: mock_kite)

    instruments = await source.fetch()

    assert instruments[0].expiry is None
    assert instruments[0].strike is None
