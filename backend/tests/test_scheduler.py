"""The daily post-close pass.

Tested through run_daily_jobs with an explicit `now`, so nothing here waits
on a clock. The scheduling arithmetic is tested separately -- getting "next
16:00 IST" wrong by a day is the kind of bug that only shows up as silence.
"""

from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

from backend import scheduler
from backend.engine.session import IST
from backend.prefs import PrefsStore
from backend.suggestions.store import SuggestionStore


@pytest.fixture
def mongo():
    return AsyncMongoMockClient()["test_db"]


# ---------------------------------------------------------------------------
# Scheduling arithmetic
# ---------------------------------------------------------------------------

def test_next_run_is_later_today_when_the_hour_has_not_passed():
    now = datetime(2024, 1, 15, 9, 0, tzinfo=IST)
    assert scheduler.seconds_until_next_run(now) == 7 * 3600


def test_next_run_rolls_to_tomorrow_once_the_hour_has_passed():
    now = datetime(2024, 1, 15, 16, 30, tzinfo=IST)
    assert scheduler.seconds_until_next_run(now) == pytest.approx(23.5 * 3600)


def test_scheduling_is_computed_in_ist_not_utc():
    """23:00 IST is 17:30 UTC the same day; a UTC-based calculation would
    think 16:00 was still seven hours away instead of tomorrow."""
    now = datetime(2024, 1, 15, 23, 0, tzinfo=IST)
    assert scheduler.seconds_until_next_run(now) == pytest.approx(17 * 3600)


# ---------------------------------------------------------------------------
# The pass itself
# ---------------------------------------------------------------------------

async def _add_user(mongo, user_id: str) -> None:
    await mongo["users"].insert_one({"id": user_id, "google_sub": user_id, "email": f"{user_id}@x.com",
                                     "name": user_id, "picture": None,
                                     "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)})


@pytest.mark.asyncio
async def test_pass_scans_for_each_enabled_user(mongo, monkeypatch):
    await _add_user(mongo, "alice")
    await _add_user(mongo, "bob")
    scanned = []

    async def fake_scan(db, user_id, universe, **kwargs):
        scanned.append((user_id, kwargs["source"]))
        return []

    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    result = await scheduler.run_daily_jobs(mongo, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert sorted(scanned) == [("alice", "scheduler"), ("bob", "scheduler")]
    assert result["users"] == 2


@pytest.mark.asyncio
async def test_pass_skips_users_who_turned_scanning_off(mongo, monkeypatch):
    await _add_user(mongo, "alice")
    await _add_user(mongo, "bob")
    await PrefsStore(mongo).update("bob", {"scan_enabled": False})
    scanned = []

    async def fake_scan(db, user_id, universe, **kwargs):
        scanned.append(user_id)
        return []

    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    await scheduler.run_daily_jobs(mongo, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert scanned == ["alice"]


@pytest.mark.asyncio
async def test_one_users_failure_does_not_stop_the_others(mongo, monkeypatch):
    await _add_user(mongo, "alice")
    await _add_user(mongo, "bob")

    async def fake_scan(db, user_id, universe, **kwargs):
        if user_id == "alice":
            raise RuntimeError("yfinance said no")
        return []

    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    result = await scheduler.run_daily_jobs(mongo, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert result["users"] == 1


@pytest.mark.asyncio
async def test_pass_expires_stale_pending_suggestions(mongo, monkeypatch):
    now = datetime(2024, 1, 15, tzinfo=timezone.utc)
    store = SuggestionStore(mongo)
    await mongo["suggestions"].insert_one({
        "id": "s1", "user_id": "alice", "symbol": "RELIANCE", "mode": "LONGTERM",
        "status": "PENDING", "created_at": now - timedelta(days=9),
        "expires_at": now - timedelta(days=6),
    })

    async def fake_scan(db, user_id, universe, **kwargs):
        return []

    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    result = await scheduler.run_daily_jobs(mongo, now=now)

    assert result["expired"] == 1
    assert (await store.get("alice", "s1"))["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_new_suggestions_get_a_thesis(mongo, monkeypatch):
    await _add_user(mongo, "alice")
    created = [{"id": "s1", "symbol": "RELIANCE"}]

    async def fake_scan(db, user_id, universe, **kwargs):
        await mongo["suggestions"].insert_one({
            "id": "s1", "user_id": "alice", "symbol": "RELIANCE", "mode": "LONGTERM",
            "status": "PENDING", "ai_thesis": None,
        })
        return created

    class _Agent:
        async def run(self, symbol):
            return type("R", (), {"thesis": f"{symbol} is compounding.", "analyst_summary": ""})()

    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)
    monkeypatch.setattr(
        scheduler, "attach_theses",
        lambda db, user_id, suggestions: __import__(
            "backend.suggestions.thesis", fromlist=["attach_theses"]
        ).attach_theses(db, user_id, suggestions, agent=_Agent()),
    )

    await scheduler.run_daily_jobs(mongo, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert (await SuggestionStore(mongo).get("alice", "s1"))["ai_thesis"] == "RELIANCE is compounding."
