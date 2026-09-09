"""The one place that knows which brokers exist. Adding a fourth means one
new adapter file and one new line in BROKERS -- nothing else in the app
should need to change (docs/ROADMAP.md Phase 2's done-when criterion)."""

from backend.brokers.angel_one import AngelOneAdapter
from backend.brokers.kite import KiteAdapter
from backend.brokers.protocol import BrokerAdapter
from backend.brokers.upstox import UpstoxAdapter

BROKERS = {
    "kite": lambda creds, redis, user_id: KiteAdapter(
        api_key=creds.api_key if creds else None,
        api_secret=creds.api_secret if creds else None,
        redis=redis, user_id=user_id,
    ),
    "upstox": lambda creds, redis, user_id: UpstoxAdapter(
        api_key=creds.api_key if creds else None,
        api_secret=creds.api_secret if creds else None,
        redirect_uri=creds.extra if creds else None,
        redis=redis, user_id=user_id,
    ),
    "angel_one": lambda creds, redis, user_id: AngelOneAdapter(
        api_key=creds.api_key if creds else None,
        api_secret=creds.api_secret if creds else None,
        redis=redis, user_id=user_id,
    ),
}


class UnknownBroker(ValueError):
    pass


async def get_broker_adapter(broker: str, user_id: str, credentials, redis) -> BrokerAdapter:
    try:
        build = BROKERS[broker]
    except KeyError:
        raise UnknownBroker(f"Unknown broker: {broker!r}. Known: {sorted(BROKERS)}") from None

    creds = await credentials.get(user_id, broker)
    return build(creds, redis, user_id)
