"""refresh_from_kite_if_connected: the bundled seed file (~130 large-caps)
is a floor, not the real universe -- this is what actually expands the
instrument master to Kite's full NSE+BSE dump once a session is connected,
and it must never raise regardless of why it can't (no session, expired
session, database down)."""

from unittest.mock import AsyncMock, MagicMock

from backend.auth.kite_session import KiteSessionState
from backend.instruments import loader


async def test_no_op_when_kite_session_is_not_active(monkeypatch):
    fake_session = MagicMock()
    fake_session.state = AsyncMock(return_value=KiteSessionState.NEEDS_LOGIN)
    monkeypatch.setattr("backend.auth.kite_session.KiteSessionManager", lambda *a, **kw: fake_session)

    result = await loader.refresh_from_kite_if_connected()

    assert result == 0


async def test_refreshes_both_nse_and_bse_when_active(monkeypatch):
    monkeypatch.setattr("backend.database.db.db", MagicMock())

    fake_session = MagicMock()
    fake_session.state = AsyncMock(return_value=KiteSessionState.ACTIVE)
    fake_session.get_access_token = AsyncMock(return_value="tok")
    monkeypatch.setattr("backend.auth.kite_session.KiteSessionManager", lambda *a, **kw: fake_session)

    captured = {}

    class _FakeSource:
        def __init__(self, kite_client_factory, exchanges):
            captured["exchanges"] = exchanges

    monkeypatch.setattr("backend.instruments.kite_source.KiteInstrumentSource", _FakeSource)
    monkeypatch.setattr(loader, "refresh_instruments", AsyncMock(return_value=1847))

    result = await loader.refresh_from_kite_if_connected()

    assert result == 1847
    assert captured["exchanges"] == ("NSE", "BSE")


async def test_never_raises_and_returns_zero_on_any_failure(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("redis is down")

    monkeypatch.setattr("backend.auth.kite_session.KiteSessionManager", _boom)

    result = await loader.refresh_from_kite_if_connected()

    assert result == 0
