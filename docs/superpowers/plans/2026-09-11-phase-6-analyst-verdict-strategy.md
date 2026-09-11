# Phase 6 — Analyst-Verdict Strategy + Dead-Code Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the confirmed-dead `MasterAgent`-era code, and add one new LONGTERM strategy
whose entry signal is genuinely LLM/analyst-derived — plus turn on `QualityMomentumStrategy`,
which has been silently inert in production since it was written.

**Architecture:** A new Redis-cached "analyst verdict" per curated symbol (mirroring
`backend/ai/sentiment.py`'s existing cache-then-read shape), refreshed once daily by the
scheduler and read by a new `AnalystVerdictStrategy` via the same pre-built-dict pattern
`QualityMomentumStrategy` already established. Both strategies get wired into
`scan_universe`, the real production path for LONGTERM suggestion generation — the one place
that was missing for `QualityMomentumStrategy` already.

**Tech Stack:** Python 3.12, FastAPI, Motor/MongoDB (mongomock-motor in tests), Redis
(unittest.mock.AsyncMock in tests), pytest + pytest-asyncio, pydantic v2.

**Spec:** `docs/superpowers/specs/2026-09-11-phase-6-analyst-verdict-strategy-design.md`

## Global Constraints

- `Strategy.on_bar` must stay synchronous and I/O-free (enforced by
  `tests/test_no_network_in_strategies.py` and `backend/strategies/base.py`'s own docstring)
  — all async/LLM work happens before `build_default_strategies` is called, never inside a
  strategy.
- No revival of the `confidence*0.6 + alignment*0.4` blend, or of `MasterAgent`'s decision
  node. `ResearchAgent` (`backend/research/graph.py`) stays thesis-only.
- `AnalystVerdictStrategy`'s `Intent.strength` must be clamped to `[0, 1]` before
  construction — `AnalystAgent`'s LLM-supplied `sentiment_score` is not validated to stay
  within `[-1, 1]` at its source (`components/analyst/sentiment.py` does a bare
  `float(data.get("score", 0.0))`), and `Intent.__post_init__` raises on an out-of-range
  `strength` with nothing upstream catching it inside `runner.run()`'s `on_bar` call — an
  unclamped value would crash every user's daily scan, not just this one symbol.
- Only `KiteInstrumentSource`-style narrow scoping applies here too: the new strategy's daily
  pre-fetch covers only `backend.options.resolver.STRIKE_INTERVALS`' curated symbols, never
  the full scan universe — real LLM cost per symbol.
- Every existing test must keep passing unchanged after every task
  (`cd backend && python -m pytest`).

---

### Task 1: Delete confirmed-dead code

**Files:**
- Delete: `backend/components/quant/agent.py`
- Delete: `backend/components/risk/agent.py`
- Delete: `backend/components/quant/strategies.py`
- Delete: `backend/tests/test_signal_integrity.py`

**Interfaces:** None — this task has no consumers and no producers. Verified (grep across
the whole `backend/` tree) that nothing outside these four files references
`QuantAgent`/`RiskAgent`/`TechnicalBreakout`/`MeanReversion`/`VolumeSurge`/`MACDCrossover`
from `components.quant`/`components.risk` — the real strategies with those same names live in
`backend/strategies/{longterm,intraday}/` and are untouched.

- [ ] **Step 1: Delete the four files**

```bash
git rm backend/components/quant/agent.py backend/components/risk/agent.py backend/components/quant/strategies.py backend/tests/test_signal_integrity.py
```

- [ ] **Step 2: Confirm nothing else imports the deleted modules**

Run: `cd backend && grep -rn "components.quant.agent\|components.risk.agent\|components\.quant\.strategies" --include=*.py . | grep -v __pycache__`
Expected: no output (empty).

- [ ] **Step 3: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS, with 6 fewer tests collected than before (the 6 tests in
`test_signal_integrity.py`).

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor: delete dead MasterAgent-era quant/risk agent code (Phase 6)

components/quant/agent.py and components/risk/agent.py haven't been
reachable since MasterAgent was demoted to ResearchAgent (commit
6958540). Their strategies were separately ported to real Strategy
classes in Phase 4. test_signal_integrity.py's entire subject (the old
TradeSignal/RiskAgent machinery, including the confidence*0.6+
alignment*0.4 blend the 30% AI cap exists to prevent) is gone with it;
the defect classes it guarded against are already structurally
prevented in the current code (Side enum comparison-by-identity,
Intent.__post_init__).
EOF
)"
```

---

### Task 2: Analyst-verdict cache + scheduler refresh

**Files:**
- Create: `backend/ai/analyst_verdict.py`
- Modify: `backend/scheduler.py`
- Test: `backend/tests/test_ai_analyst_verdict.py` (new), `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `AnalystAgent` (existing, `backend/components/analyst/agent.py`),
  `STRIKE_INTERVALS` (existing, `backend/options/resolver.py`).
- Produces: `async get_cached_verdict(symbol: str, redis) -> Optional[dict]`,
  `async refresh_analyst_verdict(symbol: str, redis, ttl_seconds: int = 90000) -> dict` — the
  returned/cached dict shape is
  `{"sentiment_score": float, "impact_score": int, "label": str, "top_reason": str}`.

- [ ] **Step 1: Write failing tests for the cache read/write functions**

```python
# backend/tests/test_ai_analyst_verdict.py
import json
from unittest.mock import AsyncMock

import pytest

from backend.ai.analyst_verdict import get_cached_verdict, refresh_analyst_verdict


@pytest.mark.asyncio
async def test_get_cached_verdict_miss_returns_none():
    redis = AsyncMock()
    redis.get.return_value = None
    result = await get_cached_verdict("RELIANCE", redis)
    assert result is None
    redis.get.assert_awaited_once_with("analyst_verdict:RELIANCE")


@pytest.mark.asyncio
async def test_get_cached_verdict_hit_returns_dict():
    redis = AsyncMock()
    redis.get.return_value = json.dumps({
        "sentiment_score": 0.5, "impact_score": 7, "label": "bullish", "top_reason": "x",
    })
    result = await get_cached_verdict("RELIANCE", redis)
    assert result["label"] == "bullish"
    assert result["impact_score"] == 7


@pytest.mark.asyncio
async def test_get_cached_verdict_redis_failure_returns_none():
    redis = AsyncMock()
    redis.get.side_effect = OSError("Name or service not known")
    result = await get_cached_verdict("RELIANCE", redis)
    assert result is None


class _FakeAnalystAgent:
    async def analyze(self, state):
        return {
            "sentiment_score": 0.5, "impact_score": 7,
            "summary": "Strong quarter driven by margin expansion.\nRisks remain elevated.",
            "events": [{
                "event_type": "earnings", "description": "Beat estimates by 12%",
                "date": "2024-01-01T00:00:00", "symbols": ["RELIANCE"], "impact_rating": 8,
            }],
            "sentiment_analysis": {"score": 0.5, "label": "bullish", "risk_score": 7, "article_count": 3},
        }


@pytest.mark.asyncio
async def test_refresh_analyst_verdict_caches_and_returns(monkeypatch):
    monkeypatch.setattr("backend.components.analyst.agent.AnalystAgent", _FakeAnalystAgent)
    redis = AsyncMock()

    verdict = await refresh_analyst_verdict("RELIANCE", redis)

    assert verdict == {
        "sentiment_score": 0.5, "impact_score": 7, "label": "bullish",
        "top_reason": "Beat estimates by 12%",
    }
    redis.set.assert_awaited_once()
    args, kwargs = redis.set.await_args
    assert args[0] == "analyst_verdict:RELIANCE"
    assert json.loads(args[1]) == verdict
    assert kwargs["ex"] == 90000


class _NoEventsAgent:
    async def analyze(self, state):
        return {
            "sentiment_score": 0.2, "impact_score": 3,
            "summary": "Modest gains this week.\nNo major catalysts.",
            "events": [], "sentiment_analysis": {"label": "neutral"},
        }


@pytest.mark.asyncio
async def test_refresh_analyst_verdict_falls_back_to_summary_without_events(monkeypatch):
    monkeypatch.setattr("backend.components.analyst.agent.AnalystAgent", _NoEventsAgent)
    redis = AsyncMock()

    verdict = await refresh_analyst_verdict("TCS", redis)

    assert verdict["top_reason"] == "Modest gains this week."
    assert verdict["label"] == "neutral"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_ai_analyst_verdict.py -v`
Expected: FAIL — `backend.ai.analyst_verdict` doesn't exist yet.

- [ ] **Step 3: Implement the cache module**

```python
# backend/ai/analyst_verdict.py
"""Analyst-verdict cache for AnalystVerdictStrategy -- mirrors backend/ai/sentiment.py's
get_cached_sentiment/refresh_sentiment shape exactly: the engine loop (and, here, the daily
scan) must never await an LLM round-trip synchronously, so the real AnalystAgent call happens
out-of-band (refresh_analyst_verdict, called by the scheduler -- see backend/scheduler.py)
and is cached in Redis; callers only ever read the cache (get_cached_verdict), which returns
None on a miss or any Redis error rather than blocking or raising.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_cached_verdict(symbol: str, redis) -> Optional[dict]:
    """Reads a Redis-cached analyst verdict. Returns None (never blocks on the LLM, never
    raises) on a cache miss, a Redis failure, or a malformed cached value."""
    key = f"analyst_verdict:{symbol}"
    try:
        val = await redis.get(key)
    except Exception as exc:
        logger.warning("analyst verdict cache unavailable for %s: %s", symbol, exc)
        return None
    if val is None:
        return None
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        logger.warning("analyst verdict cache for %s held a malformed value", symbol)
        return None


async def refresh_analyst_verdict(symbol: str, redis, ttl_seconds: int = 90000) -> dict:
    """Computes a fresh verdict (via the existing AnalystAgent) and writes it to Redis with
    the given TTL. 90000s (25h) means yesterday's verdict survives comfortably until the next
    scheduled refresh even if that run is a little early or late. Called by a background
    task/job (backend.scheduler), never by the engine loop or a Strategy directly.

    `top_reason` is a short catalyst string, not the full LLM narrative: the highest-impact
    event's description if any events were classified, otherwise the first non-empty line of
    the summary (truncated to 200 chars).
    """
    from backend.components.analyst.agent import AnalystAgent

    output = await AnalystAgent().analyze({"symbol": symbol})

    events = output.get("events") or []
    if events:
        top_event = max(events, key=lambda e: e.get("impact_rating", 0))
        top_reason = top_event.get("description", "")
    else:
        summary = output.get("summary") or ""
        top_reason = next((line.strip() for line in summary.splitlines() if line.strip()), "")[:200]

    verdict = {
        "sentiment_score": float(output.get("sentiment_score", 0.0)),
        "impact_score": int(output.get("impact_score", 0)),
        "label": output.get("sentiment_analysis", {}).get("label", "neutral"),
        "top_reason": top_reason,
    }

    key = f"analyst_verdict:{symbol}"
    await redis.set(key, json.dumps(verdict), ex=ttl_seconds)
    logger.info("Refreshed analyst verdict for %s: %s", symbol, verdict["label"])
    return verdict
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ai_analyst_verdict.py -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for the scheduler wiring**

```python
# backend/tests/test_scheduler.py -- add near the top imports
from unittest.mock import AsyncMock
```

```python
# backend/tests/test_scheduler.py -- add as new tests
from backend.options.resolver import STRIKE_INTERVALS


@pytest.mark.asyncio
async def test_pass_refreshes_analyst_verdicts_for_curated_symbols(mongo, monkeypatch):
    async def fake_scan(db, user_id, universe, **kwargs):
        return []
    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    refreshed = []

    async def fake_refresh(symbol, redis, **kwargs):
        refreshed.append(symbol)
        return {}
    monkeypatch.setattr(scheduler, "refresh_analyst_verdict", fake_refresh)

    redis = AsyncMock()
    result = await scheduler.run_daily_jobs(mongo, redis=redis, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert set(refreshed) == set(STRIKE_INTERVALS)
    assert result["verdicts_refreshed"] == len(STRIKE_INTERVALS)


@pytest.mark.asyncio
async def test_pass_skips_analyst_verdict_refresh_without_redis(mongo, monkeypatch):
    async def fake_scan(db, user_id, universe, **kwargs):
        return []
    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    called = []

    async def fake_refresh(symbol, redis, **kwargs):
        called.append(symbol)
        return {}
    monkeypatch.setattr(scheduler, "refresh_analyst_verdict", fake_refresh)

    result = await scheduler.run_daily_jobs(mongo, redis=None, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert called == []
    assert result["verdicts_refreshed"] == 0


@pytest.mark.asyncio
async def test_one_symbols_verdict_refresh_failure_does_not_stop_the_others(mongo, monkeypatch):
    async def fake_scan(db, user_id, universe, **kwargs):
        return []
    monkeypatch.setattr(scheduler, "scan_universe", fake_scan)

    async def flaky_refresh(symbol, redis, **kwargs):
        if symbol == "TCS":
            raise RuntimeError("LLM timeout")
        return {}
    monkeypatch.setattr(scheduler, "refresh_analyst_verdict", flaky_refresh)

    redis = AsyncMock()
    result = await scheduler.run_daily_jobs(mongo, redis=redis, now=datetime(2024, 1, 15, tzinfo=timezone.utc))

    assert result["verdicts_refreshed"] == len(STRIKE_INTERVALS) - 1
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scheduler.py -k verdict -v`
Expected: FAIL — `scheduler.refresh_analyst_verdict` doesn't exist as a module attribute yet,
and `run_daily_jobs`'s result has no `"verdicts_refreshed"` key.

- [ ] **Step 7: Implement the scheduler wiring**

In `backend/scheduler.py`, add the import:

```python
from backend.ai.analyst_verdict import refresh_analyst_verdict
from backend.options.resolver import STRIKE_INTERVALS
```

Add a new helper (near `_refresh_sentiment_for`):

```python
async def _refresh_analyst_verdicts(redis) -> int:
    """Shared across every user's scan -- one refresh per curated symbol per day, not one
    per user. Same per-symbol failure isolation _refresh_sentiment_for already uses: one bad
    symbol must not cost every other symbol its refresh."""
    if redis is None:
        return 0
    count = 0
    for symbol in STRIKE_INTERVALS:
        try:
            await refresh_analyst_verdict(symbol, redis)
            count += 1
        except Exception as exc:
            logger.warning("analyst verdict refresh failed for %s: %s", symbol, exc)
    return count
```

In `run_daily_jobs`, add the call right after `options_closed` and thread the count through:

```python
    expired = await SuggestionStore(db).expire_stale(now=now)
    options_closed = await close_expired_option_positions(db, redis=redis, now=now)
    verdicts_refreshed = await _refresh_analyst_verdicts(redis)
```

Update the `logger.info` call and the `return` statement:

```python
    logger.info(
        "daily pass: %d expired, %d option position(s) closed, %d verdict(s) refreshed, "
        "%d user(s) scanned, %d suggestion(s) created",
        expired, options_closed, verdicts_refreshed, scanned_users, created_total,
    )
    return {
        "expired": expired, "options_closed": options_closed,
        "verdicts_refreshed": verdicts_refreshed,
        "users": scanned_users, "created": created_total,
    }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scheduler.py -k verdict -v`
Expected: PASS

- [ ] **Step 9: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/ai/analyst_verdict.py backend/scheduler.py backend/tests/test_ai_analyst_verdict.py backend/tests/test_scheduler.py
git commit -m "$(cat <<'EOF'
feat: analyst-verdict cache + daily scheduler refresh (Phase 6)

Mirrors backend/ai/sentiment.py's cache-then-read shape: the real
AnalystAgent call happens once a day, shared across every user's scan,
never inside the engine loop or a Strategy.
EOF
)"
```

---

### Task 3: `AnalystVerdictStrategy` + registry wiring

**Files:**
- Create: `backend/strategies/longterm/analyst_verdict.py`
- Modify: `backend/strategies/registry.py`
- Test: `backend/tests/test_strategies_ported.py`

**Interfaces:**
- Consumes: `get_cached_verdict`'s cached shape (Task 2) as the `verdicts` constructor arg.
- Produces: `AnalystVerdictStrategy(universe: list[str], symbol_for_token: dict[int, str],
  verdicts: dict[str, dict])`; `build_default_strategies(..., analyst_verdicts:
  Optional[dict[str, dict]] = None)`.

- [ ] **Step 1: Write failing tests for the strategy**

```python
# backend/tests/test_strategies_ported.py -- add near the end, in its own section
from backend.strategies.longterm.analyst_verdict import AnalystVerdictStrategy


def _bullish_verdict(**overrides) -> dict:
    verdict = {"sentiment_score": 0.6, "impact_score": 8, "label": "bullish", "top_reason": "Beat estimates by 12%"}
    verdict.update(overrides)
    return verdict


def test_analyst_verdict_strategy_fires_on_bullish_high_impact_verdict():
    strategy = AnalystVerdictStrategy([SYMBOL], {TOKEN: SYMBOL}, {SYMBOL: _bullish_verdict()})
    intents = _run(strategy, _flat_bars(1))

    assert len(intents) == 1
    intent = intents[0]
    assert intent.side == Side.BUY
    assert intent.reason_codes == ["analyst_bullish_verdict", "Beat estimates by 12%"]
    assert intent.strength == pytest.approx(0.8)  # (0.6 + 1) / 2


def test_analyst_verdict_strategy_silent_below_impact_threshold():
    strategy = AnalystVerdictStrategy([SYMBOL], {TOKEN: SYMBOL}, {SYMBOL: _bullish_verdict(impact_score=3)})
    intents = _run(strategy, _flat_bars(1))
    assert intents == []


def test_analyst_verdict_strategy_silent_when_not_bullish():
    strategy = AnalystVerdictStrategy([SYMBOL], {TOKEN: SYMBOL}, {SYMBOL: _bullish_verdict(label="neutral")})
    intents = _run(strategy, _flat_bars(1))
    assert intents == []


def test_analyst_verdict_strategy_silent_for_symbol_with_no_verdict():
    strategy = AnalystVerdictStrategy([SYMBOL], {TOKEN: SYMBOL}, {})
    intents = _run(strategy, _flat_bars(1))
    assert intents == []


def test_analyst_verdict_strategy_clamps_out_of_range_sentiment_score():
    # A hallucinated LLM score outside [-1, 1] must not crash Intent construction.
    strategy = AnalystVerdictStrategy([SYMBOL], {TOKEN: SYMBOL}, {SYMBOL: _bullish_verdict(sentiment_score=1.4)})
    intents = _run(strategy, _flat_bars(1))
    assert len(intents) == 1
    assert intents[0].strength == 1.0


def test_build_default_strategies_includes_analyst_verdict_when_provided():
    strategies = build_default_strategies(
        universe=[SYMBOL],
        analyst_verdicts={SYMBOL: _bullish_verdict()},
    )
    assert len(strategies) == 9

    verdict_strategy = next(s for s in strategies if s.spec.name == "analyst_verdict")
    assert verdict_strategy.spec.mode == "LONGTERM"
    assert verdict_strategy.spec.timeframe == "1d"
    assert verdict_strategy.spec.universe == [SYMBOL]
```

`pytest` needs importing in this file if not already (check the top of
`tests/test_strategies_ported.py` — it currently has no `import pytest` line since it uses
plain assert-based tests; add `import pytest` alongside the existing imports for
`pytest.approx`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_strategies_ported.py -k analyst_verdict -v`
Expected: FAIL — `backend.strategies.longterm.analyst_verdict` doesn't exist yet.

- [ ] **Step 3: Implement the strategy**

```python
# backend/strategies/longterm/analyst_verdict.py
"""A LONGTERM strategy whose entry signal is genuinely analyst/LLM-derived, not a technical
indicator -- the concrete substance of ROADMAP.md Phase 6's "give long-term suggestions a
genuine reasoning source". `verdicts` is precomputed by backend/ai/analyst_verdict.py's
cache-then-read shape and handed in at construction, same pattern
backend/strategies/longterm/quality_momentum.py already established: this module does NO I/O
of its own, per the project's no-I/O-in-strategies rule
(backend/tests/test_no_network_in_strategies.py).
"""

from backend.core.models import Intent, Side
from backend.engine.protocols import StrategySpec
from backend.strategies.base import TokenResolvingStrategy

# 1-10 scale (backend.components.shared.models.NewsArticle.impact_score's own range) -- below
# this, routine/low-consequence news shouldn't be enough to trigger a trade.
MATERIALITY_THRESHOLD = 6


class AnalystVerdictStrategy(TokenResolvingStrategy):
    """BUY when the symbol's cached analyst verdict is bullish and material. `verdicts` is a
    symbol -> {"sentiment_score", "impact_score", "label", "top_reason"} lookup for the same
    curated universe this strategy trades."""

    def __init__(
        self,
        universe: list[str],
        symbol_for_token: dict[int, str],
        verdicts: dict[str, dict],
    ) -> None:
        super().__init__(universe, symbol_for_token)
        self.verdicts = verdicts
        self.spec = StrategySpec(
            name="analyst_verdict", mode="LONGTERM", timeframe="1d",
            warmup_bars=1, universe=universe,
        )

    def on_bar(self, ctx, bar) -> None:
        symbol = self.symbol_for(bar)
        if symbol is None or symbol not in self.verdicts:
            return

        verdict = self.verdicts[symbol]
        if verdict["label"] != "bullish" or verdict["impact_score"] < MATERIALITY_THRESHOLD:
            return

        history = ctx.history(symbol, 1)
        if not history:
            return
        current_price = history[-1].close

        # The cached sentiment_score comes from an LLM call with no upstream range
        # validation -- clamp defensively so a hallucinated value can never raise out of
        # Intent's own [0, 1] strength check and take down the whole scan.
        strength = max(0.0, min(1.0, (verdict["sentiment_score"] + 1) / 2))

        ctx.submit(Intent(
            symbol=symbol, side=Side.BUY, strength=strength,
            reason_codes=["analyst_bullish_verdict", verdict["top_reason"]],
            stop_hint=current_price * 0.90,
            target_hint=current_price * 1.15,
        ))
```

In `backend/strategies/registry.py`, add the import:

```python
from backend.strategies.longterm.analyst_verdict import AnalystVerdictStrategy
```

Add the new parameter and conditional append:

```python
def build_default_strategies(
    universe: Optional[list[str]] = None,
    symbol_for_token: Optional[dict[int, str]] = None,
    quality_universe: Optional[list[str]] = None,
    quality_scores: Optional[dict[str, float]] = None,
    analyst_verdicts: Optional[dict[str, dict]] = None,
) -> list[Strategy]:
```

Update the docstring's `quality_universe`/`quality_scores` paragraph by adding one more,
directly after it:

```python
    `analyst_verdicts` (Phase 6) is the pre-built output of
    `backend.ai.analyst_verdict.get_cached_verdict` per symbol -- a Redis read, so this
    factory can't do it itself either. Default `None` means "don't include
    AnalystVerdictStrategy"; the caller (backend.suggestions.scan.scan_universe) is expected
    to have already fetched it for the curated symbol list in
    `backend.options.resolver.STRIKE_INTERVALS`.
```

And append the conditional strategy, after the existing `quality_universe`/`quality_scores`
block:

```python
    if quality_universe is not None and quality_scores is not None:
        strategies.append(
            QualityMomentumStrategy(quality_universe, symbol_for_token, quality_scores)
        )
    if analyst_verdicts is not None:
        strategies.append(
            AnalystVerdictStrategy(list(analyst_verdicts.keys()), symbol_for_token, analyst_verdicts)
        )
    return strategies
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_strategies_ported.py -v`
Expected: PASS — including the existing `test_build_default_strategies_returns_expected_eight`
(unaffected: it doesn't pass `analyst_verdicts`, so the default `None` keeps the count at 8)
and the new `test_build_default_strategies_includes_analyst_verdict_when_provided` from
Step 1.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/strategies/longterm/analyst_verdict.py backend/strategies/registry.py backend/tests/test_strategies_ported.py
git commit -m "$(cat <<'EOF'
feat: AnalystVerdictStrategy -- genuine LLM-derived LONGTERM signal (Phase 6)

Wired into build_default_strategies via the same pre-built-dict pattern
QualityMomentumStrategy already established. sentiment_score is clamped
defensively since it comes from an unvalidated LLM response.
EOF
)"
```

---

### Task 4: `build_quality_universe` returns scores, not just a filtered list

**Files:**
- Modify: `backend/screening/universe.py`
- Test: `backend/tests/test_screening_universe.py`

**Interfaces:**
- Produces: `async build_quality_universe(instruments: list[Instrument], provider:
  FundamentalsProvider, min_quality_score: float = 0.5) -> dict[str, float]` (was
  `-> list[str]`).

- [ ] **Step 1: Update the two shape-dependent tests to the new return type**

```python
# backend/tests/test_screening_universe.py -- replace these two test bodies
async def test_build_quality_universe_excludes_none_and_raising():
    instruments = [_instrument("A"), _instrument("B"), _instrument("C")]
    provider = FakeProvider(
        snapshots={"A": _HIGH_QUALITY, "B": _HIGH_QUALITY, "C": _HIGH_QUALITY},
        raising=["B"], none_for=["C"],
    )

    result = await build_quality_universe(instruments, provider, min_quality_score=0.0)

    assert result == {"A": quality_score(_HIGH_QUALITY.model_copy(update={"symbol": "A"}))}


async def test_build_quality_universe_applies_threshold():
    instruments = [_instrument("HIGH"), _instrument("LOW")]
    provider = FakeProvider(snapshots={"HIGH": _HIGH_QUALITY, "LOW": _LOW_QUALITY})

    result = await build_quality_universe(instruments, provider, min_quality_score=0.5)

    assert result == {"HIGH": quality_score(_HIGH_QUALITY.model_copy(update={"symbol": "HIGH"}))}
```

`test_build_quality_universe_caps_concurrency` needs its one shape-dependent line updated too
(`len(result) == 25` still works against a dict, no other change needed there).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_screening_universe.py -v`
Expected: FAIL — `build_quality_universe` still returns a `list[str]`, so
`result == {"A": ...}` fails.

- [ ] **Step 3: Implement**

In `backend/screening/universe.py`, change the return statement and the docstring/type hint:

```python
async def build_quality_universe(
    instruments: list[Instrument],
    provider: FundamentalsProvider,
    min_quality_score: float = 0.5,
) -> dict[str, float]:
    """Fetches a snapshot per instrument concurrently (capped by a semaphore
    so this doesn't fire 80+ simultaneous yfinance requests), scores each,
    and returns a symbol -> quality_score mapping for tradingsymbols meeting
    `min_quality_score`. An instrument whose snapshot fetch fails or returns
    None is excluded outright -- never defaulted to a passing (or any) score.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)

    async def _fetch(instrument: Instrument) -> tuple[str, float] | None:
        async with semaphore:
            try:
                snapshot = await provider.snapshot(instrument)
            except Exception:
                return None
        if snapshot is None:
            return None
        return instrument.tradingsymbol, quality_score(snapshot)

    results = await asyncio.gather(*(_fetch(instrument) for instrument in instruments))
    return {
        symbol: score for symbol, score in (r for r in results if r is not None)
        if score >= min_quality_score
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_screening_universe.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS — no other caller of `build_quality_universe` exists yet (Task 5 adds the
first real one), so nothing else is affected.

- [ ] **Step 6: Commit**

```bash
git add backend/screening/universe.py backend/tests/test_screening_universe.py
git commit -m "$(cat <<'EOF'
refactor: build_quality_universe returns scores, not just a filtered list (Phase 6)

QualityMomentumStrategy needs the scores dict directly (used as
Intent.strength) -- the list-only return is exactly why no real caller
ever wired this up despite it being registry-ready.
EOF
)"
```

---

### Task 5: Wire both into `scan_universe`

**Files:**
- Modify: `backend/suggestions/scan.py`
- Test: `backend/tests/test_suggestion_scan.py`

**Interfaces:**
- Consumes: `get_cached_verdict` (Task 2), `build_default_strategies`'s `analyst_verdicts`
  param (Task 3), `build_quality_universe`'s new `dict[str, float]` return (Task 4).

- [ ] **Step 1: Guard the existing real-scan tests against the new network call**

`scan_universe` is about to gain a `build_quality_universe(...)` call — without a monkeypatch,
the tests that exercise the real `scan_universe` path far enough to reach the
strategy-building block would start making a real yfinance-backed network call via the real
`YFinanceFundamentalsProvider`. Add one line to each:

```python
# backend/tests/test_suggestion_scan.py -- add to the top imports
import json
from unittest.mock import AsyncMock
```

```python
# backend/tests/test_suggestion_scan.py -- add this monkeypatch line to each of these two
# tests, alongside their existing monkeypatch.setattr(scan_module, "build_default_strategies", ...) line:
#   test_scan_records_one_suggestion_per_symbol_from_the_final_session
#   test_scan_does_not_query_sentiment_for_warmup_bars
# test_scan_with_no_resolvable_symbols_returns_nothing does NOT need this guard: its
# _EmptyMaster resolves zero instruments, so scan_universe returns early (before the
# strategy-building block) and never reaches build_quality_universe at all.
    monkeypatch.setattr(scan_module, "build_quality_universe", AsyncMock(return_value={}))
```

- [ ] **Step 2: Run the existing suite to confirm it's still green with the guard in place**

Run: `cd backend && python -m pytest tests/test_suggestion_scan.py -v`
Expected: PASS (this step only adds a defensive monkeypatch to tests that don't yet exercise
the new code path — nothing should change yet).

- [ ] **Step 3: Write failing tests for the new wiring**

```python
# backend/tests/test_suggestion_scan.py -- add after the existing "scan itself" tests
@pytest.mark.asyncio
async def test_scan_wires_analyst_verdicts_into_strategy_build(mongo, monkeypatch):
    from backend.suggestions import scan as scan_module

    captured = {}

    def _spy_build(universe, symbol_for_token, **kwargs):
        captured.update(kwargs)
        return [_AlwaysBuyStrategy(universe, symbol_for_token)]

    monkeypatch.setattr(scan_module, "InstrumentMaster", _FakeMaster)
    monkeypatch.setattr(scan_module, "YFinanceProvider", _RisingHistoryProvider)
    monkeypatch.setattr(scan_module, "build_default_strategies", _spy_build)
    monkeypatch.setattr(scan_module, "build_quality_universe", AsyncMock(return_value={}))

    async def fake_get(key):
        if key == "analyst_verdict:RELIANCE":
            return json.dumps({
                "sentiment_score": 0.5, "impact_score": 7,
                "label": "bullish", "top_reason": "strong earnings",
            })
        return None  # every other key (e.g. sentiment:RELIANCE) -- no cached value

    redis = AsyncMock()
    redis.get.side_effect = fake_get

    await scan_universe(mongo, user_id="alice", universe=["RELIANCE"], redis=redis)

    assert captured["analyst_verdicts"]["RELIANCE"]["label"] == "bullish"


@pytest.mark.asyncio
async def test_scan_omits_symbols_with_no_cached_verdict(mongo, monkeypatch):
    from backend.suggestions import scan as scan_module

    captured = {}

    def _spy_build(universe, symbol_for_token, **kwargs):
        captured.update(kwargs)
        return [_AlwaysBuyStrategy(universe, symbol_for_token)]

    monkeypatch.setattr(scan_module, "InstrumentMaster", _FakeMaster)
    monkeypatch.setattr(scan_module, "YFinanceProvider", _RisingHistoryProvider)
    monkeypatch.setattr(scan_module, "build_default_strategies", _spy_build)
    monkeypatch.setattr(scan_module, "build_quality_universe", AsyncMock(return_value={}))

    redis = AsyncMock()
    redis.get.return_value = None  # nothing cached for any symbol

    await scan_universe(mongo, user_id="alice", universe=["RELIANCE"], redis=redis)

    assert captured["analyst_verdicts"] == {}


@pytest.mark.asyncio
async def test_scan_skips_analyst_verdict_fetch_without_redis(mongo, monkeypatch):
    from backend.suggestions import scan as scan_module

    captured = {}

    def _spy_build(universe, symbol_for_token, **kwargs):
        captured.update(kwargs)
        return [_AlwaysBuyStrategy(universe, symbol_for_token)]

    monkeypatch.setattr(scan_module, "InstrumentMaster", _FakeMaster)
    monkeypatch.setattr(scan_module, "YFinanceProvider", _RisingHistoryProvider)
    monkeypatch.setattr(scan_module, "build_default_strategies", _spy_build)
    monkeypatch.setattr(scan_module, "build_quality_universe", AsyncMock(return_value={}))

    await scan_universe(mongo, user_id="alice", universe=["RELIANCE"], redis=None)

    assert captured["analyst_verdicts"] == {}


@pytest.mark.asyncio
async def test_scan_wires_quality_universe_into_strategy_build(mongo, monkeypatch):
    from backend.suggestions import scan as scan_module

    captured = {}

    def _spy_build(universe, symbol_for_token, **kwargs):
        captured.update(kwargs)
        return [_AlwaysBuyStrategy(universe, symbol_for_token)]

    monkeypatch.setattr(scan_module, "InstrumentMaster", _FakeMaster)
    monkeypatch.setattr(scan_module, "YFinanceProvider", _RisingHistoryProvider)
    monkeypatch.setattr(scan_module, "build_default_strategies", _spy_build)
    monkeypatch.setattr(scan_module, "build_quality_universe", AsyncMock(return_value={"RELIANCE": 0.8}))

    await scan_universe(mongo, user_id="alice", universe=["RELIANCE"])

    assert captured["quality_scores"] == {"RELIANCE": 0.8}
    assert captured["quality_universe"] == ["RELIANCE"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_suggestion_scan.py -k "wires or omits or skips" -v`
Expected: FAIL — `scan_universe` doesn't pass `analyst_verdicts`/`quality_universe`/
`quality_scores` to `build_default_strategies` yet, so `captured` won't have those keys.

- [ ] **Step 5: Implement the wiring**

In `backend/suggestions/scan.py`, add the imports:

```python
from backend.ai.analyst_verdict import get_cached_verdict
from backend.options.resolver import STRIKE_INTERVALS
from backend.screening.providers.yfinance_fundamentals import YFinanceFundamentalsProvider
from backend.screening.universe import build_quality_universe
```

Replace the strategy-building block:

```python
    symbol_for_token = {i.instrument_token: i.tradingsymbol for i in instruments}

    analyst_verdicts = {}
    if redis is not None:
        for symbol in STRIKE_INTERVALS:
            verdict = await get_cached_verdict(symbol, redis)
            if verdict is not None:
                analyst_verdicts[symbol] = verdict

    quality_scores = await build_quality_universe(instruments, YFinanceFundamentalsProvider())

    strategies = [
        s for s in build_default_strategies(
            universe=[i.tradingsymbol for i in instruments], symbol_for_token=symbol_for_token,
            quality_universe=list(quality_scores), quality_scores=quality_scores,
            analyst_verdicts=analyst_verdicts,
        )
        if s.spec.mode == "LONGTERM"
    ]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_suggestion_scan.py -v`
Expected: PASS

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && python -m pytest`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/suggestions/scan.py backend/tests/test_suggestion_scan.py
git commit -m "$(cat <<'EOF'
feat: wire analyst verdicts + quality universe into scan_universe (Phase 6)

QualityMomentumStrategy has been registry-ready but never actually
reachable in production since it was written -- this is the missing
call site for both it and the new AnalystVerdictStrategy.
EOF
)"
```

---

## After all tasks: update ROADMAP.md

Not a numbered task (docs-only, no test cycle) — mark Phase 6 done in `docs/ROADMAP.md`'s
status table and add a "What landed" section under Phase 6's own heading, the same way
Phase 5a/5b's own commits did. Note explicitly that `AnalystVerdictStrategy`'s curated symbol
list matches Phase 5b's F&O table (not a coincidence — reused rather than a third list), and
that ATR-based stop widening (the one piece of the old `RiskAgent` with no current
equivalent) remains a documented non-goal, not silently dropped. Commit as its own `docs:`
commit, then push.
