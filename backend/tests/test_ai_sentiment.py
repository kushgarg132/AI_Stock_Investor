"""get_cached_sentiment must never block on the LLM -- a cache miss returns
None immediately (backend.ai.sentiment), never raises."""

from unittest.mock import AsyncMock

import pytest

from backend.ai.sentiment import get_cached_sentiment


async def test_cache_miss_returns_none_without_raising():
    redis = AsyncMock()
    redis.get.return_value = None
    result = await get_cached_sentiment("RELIANCE", redis)
    assert result is None
    redis.get.assert_awaited_once_with("sentiment:RELIANCE")


async def test_cache_hit_returns_float():
    redis = AsyncMock()
    redis.get.return_value = "0.42"
    result = await get_cached_sentiment("RELIANCE", redis)
    assert result == pytest.approx(0.42)
