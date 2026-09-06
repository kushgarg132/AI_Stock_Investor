"""The daily post-close pass: scan for suggestions, refresh sentiment, expire
stale advice.

A single asyncio task rather than a scheduler dependency -- there are three
jobs, all on the same daily tick. The work itself lives in `run_daily_jobs`,
which takes `now` explicitly so it can be tested without waiting for 16:00.

ponytail: one process owns this loop. If the backend is ever run with more
than one worker, they will all fire it -- take a Redis lock before the pass
at that point.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.ai.sentiment import refresh_sentiment
from backend.engine.session import IST
from backend.prefs import PrefsStore
from backend.suggestions.scan import scan_universe
from backend.suggestions.store import SuggestionStore
from backend.suggestions.thesis import attach_theses

logger = logging.getLogger(__name__)

# 16:00 IST: half an hour after the 15:30 close, so the day's final daily
# candle is settled before the strategies read it.
RUN_HOUR = 16
RUN_MINUTE = 0

# Sentiment is cached per symbol and read by the engine's scoring path; only
# the symbols we just formed an opinion on are worth an LLM round trip.
MAX_SENTIMENT_REFRESH = 20


def seconds_until_next_run(now: datetime) -> float:
    now_ist = now.astimezone(IST)
    target = now_ist.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if target <= now_ist:
        target += timedelta(days=1)
    return (target - now_ist).total_seconds()


async def run_daily_jobs(db, redis=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    prefs_store = PrefsStore(db)

    expired = await SuggestionStore(db).expire_stale(now=now)

    scanned_users = 0
    created_total = 0
    for prefs in await prefs_store.scan_enabled_users():
        user_id = prefs["user_id"]
        try:
            created = await scan_universe(
                db, user_id=user_id, universe=prefs["universe"],
                account_size=prefs["account_size"], max_exposure=prefs["max_exposure"],
                source="scheduler", redis=redis, now=now,
            )
        except Exception as exc:
            # One user's bad universe must not cancel everyone else's scan.
            logger.exception("scheduled scan failed for %s: %s", user_id, exc)
            continue

        scanned_users += 1
        created_total += len(created)
        if created:
            await attach_theses(db, user_id, created)
            await _refresh_sentiment_for(created, redis)

    logger.info(
        "daily pass: %d expired, %d user(s) scanned, %d suggestion(s) created",
        expired, scanned_users, created_total,
    )
    return {"expired": expired, "users": scanned_users, "created": created_total}


async def _refresh_sentiment_for(suggestions: list[dict], redis) -> None:
    if redis is None:
        return
    for symbol in list(dict.fromkeys(s["symbol"] for s in suggestions))[:MAX_SENTIMENT_REFRESH]:
        try:
            await refresh_sentiment(symbol, redis)
        except Exception as exc:
            logger.warning("sentiment refresh failed for %s: %s", symbol, exc)


async def scheduler_loop(db, redis=None) -> None:
    while True:
        await asyncio.sleep(seconds_until_next_run(datetime.now(timezone.utc)))
        try:
            await run_daily_jobs(db, redis=redis)
        except Exception as exc:
            # Never let one bad day kill the loop for every day after it.
            logger.exception("daily pass failed: %s", exc)


def start(db, redis=None) -> asyncio.Task:
    return asyncio.create_task(scheduler_loop(db, redis))
