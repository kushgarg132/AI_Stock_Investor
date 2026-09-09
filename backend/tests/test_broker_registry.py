"""get_broker_adapter: the single place that knows which broker names exist
and builds the right adapter from a user's stored credentials. Adding a
fourth broker should mean adding one line here and one new adapter file --
nothing else in the app should need to change (per docs/ROADMAP.md Phase 2's
done-when criterion)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.auth.broker_credentials import BrokerCredentials
from backend.brokers.angel_one import AngelOneAdapter
from backend.brokers.kite import KiteAdapter
from backend.brokers.registry import BROKERS, UnknownBroker, get_broker_adapter
from backend.brokers.upstox import UpstoxAdapter


class _Credentials:
    def __init__(self, creds=None):
        self._creds = creds

    async def get(self, user_id, broker):
        return self._creds


async def test_kite_resolves_to_kite_adapter():
    creds = BrokerCredentials(api_key="ak", api_secret="as")
    adapter = await get_broker_adapter("kite", "alice", _Credentials(creds), redis=MagicMock())
    assert isinstance(adapter, KiteAdapter)


async def test_upstox_resolves_to_upstox_adapter():
    creds = BrokerCredentials(api_key="ak", api_secret="as", extra="https://cb")
    adapter = await get_broker_adapter("upstox", "alice", _Credentials(creds), redis=MagicMock())
    assert isinstance(adapter, UpstoxAdapter)


async def test_angel_one_resolves_to_angel_one_adapter():
    creds = BrokerCredentials(api_key="pk", api_secret="unused")
    adapter = await get_broker_adapter("angel_one", "alice", _Credentials(creds), redis=MagicMock())
    assert isinstance(adapter, AngelOneAdapter)


async def test_a_user_with_no_stored_credentials_still_gets_an_adapter():
    """UNCONFIGURED is a real, handled state -- not an error."""
    adapter = await get_broker_adapter("kite", "alice", _Credentials(None), redis=MagicMock())
    assert isinstance(adapter, KiteAdapter)


async def test_unknown_broker_raises():
    with pytest.raises(UnknownBroker):
        await get_broker_adapter("robinhood", "alice", _Credentials(None), redis=MagicMock())


def test_the_three_brokers_are_registered():
    assert set(BROKERS) == {"kite", "upstox", "angel_one"}
