"""KillSwitchStore: the persisted half of the daily loss kill-switch. Must
not re-arm on its own -- once tripped for a user's trading day, it stays
tripped regardless of how many times a new run checks it that same day.
"""

from datetime import date

from mongomock_motor import AsyncMongoMockClient

from backend.risk.kill_switch import KillSwitchStore


def _store():
    return KillSwitchStore(AsyncMongoMockClient()["test_db"])


async def test_starts_untripped():
    store = _store()
    assert await store.is_tripped("alice", date(2026, 9, 10)) is None


async def test_trip_is_recorded_and_visible():
    store = _store()
    await store.trip("alice", date(2026, 9, 10), reason="daily loss limit breached", equity=-52000.0)

    trip = await store.is_tripped("alice", date(2026, 9, 10))
    assert trip is not None
    assert trip["reason"] == "daily loss limit breached"
    assert trip["equity"] == -52000.0


async def test_tripping_again_the_same_day_does_not_move_the_first_trip_time():
    """Re-arming must never happen automatically -- a second trip call the
    same day (e.g. a restarted run re-detecting the same breach) must not
    reset when the day's trip is considered to have started."""
    store = _store()
    await store.trip("alice", date(2026, 9, 10), reason="first breach", equity=-50000.0)
    first = await store.is_tripped("alice", date(2026, 9, 10))

    await store.trip("alice", date(2026, 9, 10), reason="second breach", equity=-70000.0)
    second = await store.is_tripped("alice", date(2026, 9, 10))

    assert second["tripped_at"] == first["tripped_at"]
    assert second["reason"] == "first breach"  # the original reason, not overwritten


async def test_a_new_day_starts_untripped():
    store = _store()
    await store.trip("alice", date(2026, 9, 10), reason="breach", equity=-50000.0)

    assert await store.is_tripped("alice", date(2026, 9, 11)) is None


async def test_one_users_trip_does_not_affect_another():
    store = _store()
    await store.trip("alice", date(2026, 9, 10), reason="breach", equity=-50000.0)

    assert await store.is_tripped("bob", date(2026, 9, 10)) is None
