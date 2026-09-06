"""In-process pub/sub for the live socket.

Publishers (the engine loop, the suggestion store, the price pump) hand
events to the hub; each connection holds its own bounded queue and its own
set of topics. Delivery is never awaited on a slow consumer: a browser tab
that stops reading drops its oldest events instead of stalling the engine
that produced them.

ponytail: one process, in-memory. Two backend workers would each see only
their own publishers -- swap the fan-out for Redis pub/sub if that day comes.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Iterable

logger = logging.getLogger(__name__)

PRICE_PREFIX = "prices:"
DEFAULT_MAX_QUEUE = 100


class Connection:
    def __init__(self, user_id: str, max_queue: int = DEFAULT_MAX_QUEUE) -> None:
        self.user_id = user_id
        self.topics: set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)

    def subscribe(self, topics: Iterable[str]) -> None:
        self.topics.update(topics)

    def unsubscribe(self, topics: Iterable[str]) -> None:
        self.topics.difference_update(topics)

    def offer(self, message: dict) -> None:
        """Newest-wins: on a full queue the stalest event is discarded rather
        than the newest one, since a late price or P&L update is worth more
        than the one it replaced."""
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("dropping event for %s: queue still full", self.user_id)


class Hub:
    def __init__(self) -> None:
        self._connections: set[Connection] = set()

    def connect(self, user_id: str, max_queue: int = DEFAULT_MAX_QUEUE) -> Connection:
        connection = Connection(user_id, max_queue=max_queue)
        self._connections.add(connection)
        return connection

    def disconnect(self, connection: Connection) -> None:
        self._connections.discard(connection)

    async def publish(self, user_id: str, topic: str, event: str, data) -> None:
        message = {
            "topic": topic,
            "event": event,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        for connection in list(self._connections):
            if connection.user_id == user_id and topic in connection.topics:
                connection.offer(message)

    def subscribed_symbols(self) -> set[str]:
        """Symbols any live connection is watching -- the price pump polls
        exactly these and nothing else."""
        return {
            topic[len(PRICE_PREFIX):]
            for connection in self._connections
            for topic in connection.topics
            if topic.startswith(PRICE_PREFIX)
        }

    def users_on(self, topic: str) -> set[str]:
        return {c.user_id for c in self._connections if topic in c.topics}

    def users_watching(self, symbol: str) -> set[str]:
        topic = f"{PRICE_PREFIX}{symbol}"
        return {c.user_id for c in self._connections if topic in c.topics}


# The app's single hub; imported by publishers and by the socket route.
hub = Hub()
