"""AI sentiment off the engine's hot path.

The engine loop (backend/engine/runner.py, Task 6) must never await an LLM
round-trip synchronously -- a per-bar decision blocking on an LLM call is a
latency and reliability risk no trading loop should carry. So sentiment is
computed out-of-band (`refresh_sentiment`, called by a background job/cron --
not wired in this task) and cached in Redis; the engine only ever reads the
cache (`get_cached_sentiment`), which returns None on a miss rather than
blocking or raising. backend.scoring.composite.score_intent already treats
None as neutral (0.0).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_cached_sentiment(symbol: str, redis) -> Optional[float]:
    """Reads a Redis-cached sentiment score. Returns None (never blocks on the
    LLM) if no fresh value is cached -- score_intent above already treats None
    as 0.0/neutral, which is a safe default: an engine loop must never await an
    LLM round-trip synchronously."""
    key = f"sentiment:{symbol}"
    val = await redis.get(key)
    return float(val) if val is not None else None


async def refresh_sentiment(symbol: str, redis, ttl_seconds: int = 900) -> float:
    """Computes a fresh sentiment score (reuse analyze_sentiment_logic /
    fetch_news_logic) and writes it to Redis with the given TTL. Called by a
    background task/job, never by the engine loop directly."""
    from backend.components.analyst.news import fetch_news_logic
    from backend.components.analyst.sentiment import analyze_sentiment_logic

    articles = await fetch_news_logic(symbols=[symbol], limit=5)
    score = 0.0
    if articles:
        analyzed = await analyze_sentiment_logic(articles, target_symbol=symbol)
        if analyzed:
            score = sum(a.sentiment_score for a in analyzed) / len(analyzed)

    key = f"sentiment:{symbol}"
    await redis.set(key, score, ex=ttl_seconds)
    logger.info(f"Refreshed sentiment for {symbol}: {score:.3f} (ttl={ttl_seconds}s)")
    return score
