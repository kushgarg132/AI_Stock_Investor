"""The cached Kite access token must belong to one user, not the deployment.

Before this, every session shared the fixed Redis key `kite:access_token`, so
whoever connected last was trading for everyone.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from backend.auth.kite_session import KiteSessionManager


def _redis():
    """A dict-backed stand-in -- these tests are about which key is touched,
    so a mock that forgets the key would prove nothing."""
    store = {}
    redis = MagicMock()

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ex=None):
        store[key] = value
        return True

    async def _delete(key):
        store.pop(key, None)

    redis.get = AsyncMock(side_effect=_get)
    redis.set = AsyncMock(side_effect=_set)
    redis.delete = AsyncMock(side_effect=_delete)
    redis._store = store
    return redis


def _manager(user_id, redis):
    return KiteSessionManager(
        api_key="key", api_secret="secret", redis=redis, user_id=user_id
    )


async def test_one_users_token_is_not_visible_to_another():
    redis = _redis()

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.generate_session.return_value = {"access_token": "alice-token"}
        await _manager("alice", redis).exchange_request_token("rt-alice")

    assert await _manager("alice", redis).get_access_token() == "alice-token"
    assert await _manager("bob", redis).get_access_token() is None


async def test_each_user_keeps_their_own_token():
    redis = _redis()

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.generate_session.return_value = {"access_token": "alice-token"}
        await _manager("alice", redis).exchange_request_token("rt-alice")
        mock_cls.return_value.generate_session.return_value = {"access_token": "bob-token"}
        await _manager("bob", redis).exchange_request_token("rt-bob")

    assert await _manager("alice", redis).get_access_token() == "alice-token"
    assert await _manager("bob", redis).get_access_token() == "bob-token"


async def test_disconnecting_one_user_leaves_the_other_connected():
    redis = _redis()

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.generate_session.return_value = {"access_token": "alice-token"}
        await _manager("alice", redis).exchange_request_token("rt-alice")
        mock_cls.return_value.generate_session.return_value = {"access_token": "bob-token"}
        await _manager("bob", redis).exchange_request_token("rt-bob")

    await _manager("alice", redis).clear()

    assert await _manager("alice", redis).get_access_token() is None
    assert await _manager("bob", redis).get_access_token() == "bob-token"


async def test_the_cache_key_carries_the_user_and_the_broker():
    redis = _redis()

    with patch("backend.auth.kite_session.KiteConnect") as mock_cls:
        mock_cls.return_value.generate_session.return_value = {"access_token": "alice-token"}
        await _manager("alice", redis).exchange_request_token("rt-alice")

    key = next(iter(redis._store))
    assert "alice" in key
    assert "kite" in key
