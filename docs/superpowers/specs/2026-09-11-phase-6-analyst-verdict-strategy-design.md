# Phase 6 — analyst-verdict LONGTERM strategy + dead-code cleanup — design

Status: approved by user 2026-09-11, pending implementation plan.

## Goal

ROADMAP.md Phase 6 asks to "revive the long-term agent engine" — give long-term suggestions a
genuine reasoning source instead of reusing rule strategies, without reintroducing the old
`confidence*0.6 + alignment*0.4` conviction blend the 30% AI cap exists to prevent.

Investigation before this design (see conversation) found the underlying ask has already
partly happened: `QuantAgent`'s four strategies were ported to real `Strategy` classes in
Phase 4, and a separate, earlier session (commit `6958540`, 2026-09-05) already deliberately
killed the old `MasterAgent` decision-making pipeline for being "a second, ad hoc
decision-maker sitting next to the real one." What's left to actually build: delete the
now-confirmed-dead files, and add one new LONGTERM strategy whose entry signal is genuinely
LLM/analyst-derived (not just the existing post-hoc sentiment nudge every strategy already
gets), following the async-data-into-a-sync-strategy pattern `QualityMomentumStrategy`
already established but which was never actually wired up to run.

## Non-goals

- **No revival of `MasterAgent`/the old LangGraph decision node.** That architecture was
  deliberately killed already and stays dead — `ResearchAgent` (`backend/research/graph.py`)
  remains thesis-only, never a decision-maker.
- **No ATR-based stop-loss widening.** `RiskAgent` had this (widen a stop to 1.5× ATR when
  tighter); current strategies use flat-percentage stops and this phase doesn't change that
  — a plausible future improvement, not part of "revive the agent engine."
- **No changes to `/trading/start`'s `build_default_strategies` call.** That route drives the
  live INTRADAY runner; `scan_universe` (the daily scheduler pass) is the real production path
  for LONGTERM suggestion generation and is where both new wiring pieces (analyst verdicts,
  the quality-momentum fix) land. Leaving `trading.py` untouched matches how
  `quality_momentum` was originally scoped, and mirrors Phase 5b's own "stay focused on what
  serves the current goal" posture.
- **No full-universe LLM fetch.** `AnalystAgent`'s news-fetch + two LLM calls per symbol is
  real cost; the new strategy's daily pre-fetch covers only the curated F&O-eligible list
  already in `backend/options/resolver.py::STRIKE_INTERVALS` — reused rather than a new list.

## Architecture

### 1. Delete confirmed-dead code

- `backend/components/quant/agent.py`, `backend/components/risk/agent.py`,
  `backend/components/quant/strategies.py` — verified unused outside each other and one test
  file.
- `backend/tests/test_signal_integrity.py` — its entire subject (the old `TradeSignal`/
  `RiskAgent` machinery) is being deleted; the defect classes it guarded against (a
  string-case enum comparison bug, sentiment-direction handling) are already structurally
  prevented in the current code (`Side` enum comparison-by-identity discipline documented on
  the enum itself, `Intent.__post_init__`'s validation). Deleted outright, not salvaged.

### 2. Analyst-verdict cache — mirrors `backend/ai/sentiment.py`'s existing shape

New `backend/ai/analyst_verdict.py`:

- `get_cached_verdict(symbol: str, redis) -> Optional[dict]` — reads Redis key
  `analyst_verdict:{symbol}`, returns `None` on a miss or any Redis error (never blocks,
  never raises — same posture `get_cached_sentiment` already documents).
- `refresh_analyst_verdict(symbol: str, redis, ttl_seconds: int = 90000) -> dict` — calls the
  existing `AnalystAgent().analyze({"symbol": symbol})`, caches and returns
  `{"sentiment_score": float, "impact_score": int, "label": str, "top_reason": str}`.
  `top_reason` is a short string, not the full LLM narrative — the first sentence of
  `analyst_summary`, or the highest-impact event's description if one exists. TTL of 25 hours
  (900 + a day) means yesterday's verdict survives comfortably until the next scheduled
  refresh even if that run is a little early or late, same reasoning the existing
  15-minute sentiment TTL applies at its own (much higher-frequency) cadence.

Called once per symbol in the curated list by a new step in the daily scheduler pass — shared
across every user's scan, never per-user, same cost-sharing rationale
`backend/ai/sentiment.py`'s own docstring already states for why sentiment is cached rather
than computed inline per strategy run.

### 3. `AnalystVerdictStrategy` + `scan_universe` wiring

New `backend/strategies/longterm/analyst_verdict.py::AnalystVerdictStrategy`
(`TokenResolvingStrategy` subclass, `mode="LONGTERM"`, `timeframe="1d"`, minimal
`warmup_bars` — it needs one bar for a current price to compute `stop_hint`/`target_hint`
from, not an indicator history). Constructor: `(universe, symbol_for_token, verdicts:
dict[str, dict])` — same shape `QualityMomentumStrategy` already uses for its pre-built
`quality_scores`. `on_bar`: looks up the symbol in `verdicts`; fires a `Side.BUY` Intent only
when `verdicts[symbol]["label"] == "bullish"` and `impact_score >= MATERIALITY_THRESHOLD`
(6 on the 1-10 scale — a materiality bar so routine, low-consequence news doesn't trigger a
trade). `strength = (sentiment_score + 1) / 2` — naturally clears `RULE_FLOOR` (0.45) by
construction, since `AnalystAgent`'s own "bullish" label already requires
`sentiment_score > 0.15`, giving `strength > 0.575`. `reason_codes = ["analyst_bullish_verdict",
top_reason]` — the actual catalyst, not a generic label. Duplicate daily re-firing while
bullish is already prevented by `SuggestionSink`'s existing "one open idea per symbol"
guard — no extra dedupe needed in the strategy itself.

`backend/strategies/registry.py::build_default_strategies` gains a new optional
`analyst_verdicts: Optional[dict[str, dict]] = None` parameter, conditionally appending
`AnalystVerdictStrategy` — same conditional-append shape `quality_universe`/`quality_scores`
already use for `QualityMomentumStrategy`.

`backend/suggestions/scan.py::scan_universe` fetches `get_cached_verdict` for each symbol in
`backend.options.resolver.STRIKE_INTERVALS` before building strategies, and passes the
resulting `{symbol: verdict}` dict through as `analyst_verdicts`. A symbol with no cached
verdict (never refreshed, or a Redis miss) is simply absent from the dict — the strategy
silently produces no Intent for it, same "no floor for what we don't have" posture Phase 5b's
options resolver already established.

### 4. `QualityMomentumStrategy`'s dead wiring, fixed at the same call site

`backend/screening/universe.py::build_quality_universe`'s return type widens from `list[str]`
to `dict[str, float]` (symbol → quality score, already filtered to `>= min_quality_score`) —
the strategy needs the scores dict directly; the current list-only return is exactly why this
was never wired up despite being registry-ready. `scan_universe` calls it with a
`YFinanceFundamentalsProvider()` against the same `instruments` list it already resolves (the
user's full configured universe — a plain fundamentals fetch, not an LLM call, so no curation
cost concern the way analyst verdicts have one), then passes `quality_universe=list(scores)`
and `quality_scores=scores` through to `build_default_strategies`.

## Testing

Matches this codebase's existing pattern: `AnalystVerdictStrategy`'s trigger logic gets direct
unit tests (mocked verdicts dict, same style `test_strategies_ported.py` already uses for
every other strategy); `get_cached_verdict`/`refresh_analyst_verdict` get the same
mocked-Redis-and-AnalystAgent style `test_ai_sentiment.py` already uses for the sentiment
cache; `build_quality_universe`'s shape change updates `test_screening_universe.py`
deliberately; `scan_universe`'s new wiring gets covered in `test_suggestion_scan.py`.

## Done when

- `components/quant/agent.py`, `components/risk/agent.py`, `components/quant/strategies.py`,
  and `tests/test_signal_integrity.py` are gone; full suite still passes.
- A symbol with a cached bullish, high-impact verdict produces an `AnalystVerdictStrategy`
  Intent whose `reason_codes` name the actual catalyst, scored through the same
  `backend.scoring.composite` path as every other source (still capped at `AI_CAP`).
- `QualityMomentumStrategy` actually appears in a real `scan_universe` run's strategy list
  (not just in tests that hand-construct it), proven by a test.
- Exactly one conviction formula exists in the codebase (verified by the deletion in step 1 —
  there is no longer a second one to find).
- Full backend suite passes.
