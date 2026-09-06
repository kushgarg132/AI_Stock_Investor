"""Adapters that let stores publish without importing the socket layer.

The ledger and the suggestion store take an `on_change` callback; these build
one bound to a user, so the store stays a store and the hub stays optional.
"""

from backend.ws.hub import hub


def publisher_for(user_id: str):
    async def publish(topic: str, event: str, data) -> None:
        await hub.publish(user_id, topic, event, data)

    return publish
