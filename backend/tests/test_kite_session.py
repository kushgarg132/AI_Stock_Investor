"""KiteSessionManager: state machine + 6am-IST expiry math. `KiteConnect` is
patched at the class level throughout -- nothing here makes a real HTTP call.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.auth.kite_session import KiteSessionManager, KiteSessionState, next_6am_ist
from kiteconnect.exceptions import TokenException


def _redis(get_return=None):
    redis = MagicMock()
    redis.get = AsyncMock(return_value=get_return)
    redis.set = AsyncMock(return_value=True)
    return redis


async def test_unconfigured_when_no_api_key_or_secret():
    manager = KiteSessionManager(api_key=None, api_secret=None, redis=_redis(), user_id="alice")
    assert await manager.state() == KiteSessionState.UNCONFIGURED


async def test_unconfigured_generate_login_url_raises():
    manager = KiteSessionManager(api_key=None, api_secret=None, redis=_redis(), user_id="alice")
    with pytest.raises(RuntimeError):
        await manager.generate_login_url()


async def test_needs_login_when_configured_but_no_cached_token():
    manager = KiteSessionManager(api_key="key", api_secret="secret", redis=_redis(get_return=None), user_id="alice")
    assert await manager.state() == KiteSessionState.NEEDS_LOGIN


async def test_active_when_cached_token_passes_profile_check():
    redis = _redis(get_return="cached-token")
    manager = KiteSessionManager(api_key="key", api_secret="secret", redis=redis, user_id="alice")

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.profile.return_value = {"user_id": "AB1234"}
        assert await manager.state() == KiteSessionState.ACTIVE
        mock_cls.assert_called_with(api_key="key", access_token="cached-token")


async def test_degraded_when_kite_rejects_cached_token():
    redis = _redis(get_return="cached-token")
    manager = KiteSessionManager(api_key="key", api_secret="secret", redis=redis, user_id="alice")

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.profile.side_effect = TokenException("Token expired")
        assert await manager.state() == KiteSessionState.DEGRADED


async def test_generate_login_url_delegates_to_sdk():
    manager = KiteSessionManager(api_key="key", api_secret="secret", redis=_redis(), user_id="alice")

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.login_url.return_value = "https://kite.zerodha.com/connect/login?api_key=key&v=3"
        url = await manager.generate_login_url()

    assert url == "https://kite.zerodha.com/connect/login?api_key=key&v=3"


async def test_exchange_request_token_stores_access_token_with_expiry():
    redis = _redis()
    manager = KiteSessionManager(api_key="key", api_secret="secret", redis=redis, user_id="alice")

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.generate_session.return_value = {"access_token": "new-token", "user_id": "AB1234"}
        token = await manager.exchange_request_token("req-token-123")

    assert token == "new-token"
    mock_cls.return_value.generate_session.assert_called_once_with("req-token-123", "secret")
    redis.set.assert_called_once()
    args, kwargs = redis.set.call_args
    assert args[0] == "broker:alice:kite:access_token"
    assert args[1] == "new-token"
    assert kwargs["ex"] > 0


async def test_exchange_request_token_unconfigured_raises():
    manager = KiteSessionManager(api_key="key", api_secret=None, redis=_redis(), user_id="alice")
    with pytest.raises(RuntimeError):
        await manager.exchange_request_token("req-token")


@pytest.mark.parametrize(
    "now_utc, expected_ist_date",
    [
        # 2026-01-01 00:00 UTC == 2026-01-01 05:30 IST -- before 6am IST, so
        # expiry is later the SAME day.
        (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), (2026, 1, 1)),
        # 2026-01-01 01:00 UTC == 2026-01-01 06:30 IST -- after 6am IST, so
        # expiry rolls to the NEXT day.
        (datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), (2026, 1, 2)),
    ],
)
def test_next_6am_ist(now_utc, expected_ist_date):
    from zoneinfo import ZoneInfo

    expiry = next_6am_ist(now_utc)
    expiry_ist = expiry.astimezone(ZoneInfo("Asia/Kolkata"))

    assert (expiry_ist.year, expiry_ist.month, expiry_ist.day) == expected_ist_date
    assert (expiry_ist.hour, expiry_ist.minute, expiry_ist.second) == (6, 0, 0)
    assert expiry > now_utc
