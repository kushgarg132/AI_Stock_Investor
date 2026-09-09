"""refresh_instruments_from_kite / refresh_from_free_public_sources: the
bundled seed file (~130 large-caps) is a floor, not the real universe --
these are what actually expand the instrument master, and neither must ever
raise regardless of why it can't (no session, expired session, database
down, NSE/BSE unreachable).

The Kite refresh takes the connecting user's session explicitly: credentials
are per-user, so there is no deployment-wide session it could build itself."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.auth.kite_session import KiteSessionState
from backend.instruments import loader


def _fake_master(meta_doc=None):
    """A master whose collection.database["instrument_meta"] behaves like a
    real Mongo collection for the last-refreshed marker refresh_from_free_public_sources
    reads/writes, plus an AsyncMock upsert_many for refresh_instruments to call."""
    meta = MagicMock()
    meta.find_one = AsyncMock(return_value=meta_doc)
    meta.update_one = AsyncMock()
    master = MagicMock()
    master.collection.database.__getitem__.return_value = meta
    master.upsert_many = AsyncMock(side_effect=[3, 2])
    return master, meta


async def test_no_op_when_kite_session_is_not_active():
    fake_session = MagicMock()
    fake_session.state = AsyncMock(return_value=KiteSessionState.NEEDS_LOGIN)

    result = await loader.refresh_instruments_from_kite(fake_session, "api-key")

    assert result == 0


async def test_refreshes_both_nse_and_bse_when_active(monkeypatch):
    monkeypatch.setattr("backend.database.db.db", MagicMock())

    fake_session = MagicMock()
    fake_session.state = AsyncMock(return_value=KiteSessionState.ACTIVE)
    fake_session.get_access_token = AsyncMock(return_value="tok")

    captured = {}

    class _FakeSource:
        def __init__(self, kite_client_factory, exchanges):
            captured["exchanges"] = exchanges

    monkeypatch.setattr("backend.instruments.kite_source.KiteInstrumentSource", _FakeSource)
    monkeypatch.setattr(loader, "refresh_instruments", AsyncMock(return_value=1847))

    result = await loader.refresh_instruments_from_kite(fake_session, "api-key")

    assert result == 1847
    assert captured["exchanges"] == ("NSE", "BSE")


async def test_never_raises_and_returns_zero_on_any_failure():
    fake_session = MagicMock()
    fake_session.state = AsyncMock(side_effect=RuntimeError("redis is down"))

    result = await loader.refresh_instruments_from_kite(fake_session, "api-key")

    assert result == 0


async def test_free_sources_sum_counts_from_both_exchanges(monkeypatch):
    class _FakeNse:
        async def fetch(self):
            return ["nse-stub"] * 3

    class _FakeBse:
        async def fetch(self):
            return ["bse-stub"] * 2

    monkeypatch.setattr("backend.instruments.free_source.NseEquityListSource", _FakeNse)
    monkeypatch.setattr("backend.instruments.free_source.BseEquityListSource", _FakeBse)

    master, meta = _fake_master()

    result = await loader.refresh_from_free_public_sources(master)

    assert result == 5
    meta.update_one.assert_awaited_once()  # marker recorded so the next run can skip


async def test_free_sources_one_exchange_failing_does_not_stop_the_other(monkeypatch):
    class _FakeNse:
        async def fetch(self):
            raise RuntimeError("NSE blocked this IP")

    class _FakeBse:
        async def fetch(self):
            return ["bse-stub"]

    monkeypatch.setattr("backend.instruments.free_source.NseEquityListSource", _FakeNse)
    monkeypatch.setattr("backend.instruments.free_source.BseEquityListSource", _FakeBse)

    master, _meta = _fake_master()
    master.upsert_many = AsyncMock(return_value=1)

    result = await loader.refresh_from_free_public_sources(master)

    assert result == 1


async def test_free_sources_skip_when_refreshed_recently(monkeypatch):
    master, meta = _fake_master(
        meta_doc={"_id": "free_source_refresh", "last_refreshed_at": datetime.now(timezone.utc) - timedelta(hours=1)}
    )
    fetch_spy = AsyncMock()
    monkeypatch.setattr(loader, "refresh_instruments", fetch_spy)

    result = await loader.refresh_from_free_public_sources(master)

    assert result == 0
    fetch_spy.assert_not_called()
    meta.update_one.assert_not_called()


async def test_free_sources_refresh_again_once_the_marker_is_stale(monkeypatch):
    class _FakeNse:
        async def fetch(self):
            return ["nse-stub"]

    class _FakeBse:
        async def fetch(self):
            return ["bse-stub"]

    monkeypatch.setattr("backend.instruments.free_source.NseEquityListSource", _FakeNse)
    monkeypatch.setattr("backend.instruments.free_source.BseEquityListSource", _FakeBse)

    master, meta = _fake_master(
        meta_doc={"_id": "free_source_refresh", "last_refreshed_at": datetime.now(timezone.utc) - timedelta(hours=48)}
    )
    master.upsert_many = AsyncMock(return_value=1)

    result = await loader.refresh_from_free_public_sources(master)

    assert result == 2
    meta.update_one.assert_awaited_once()
