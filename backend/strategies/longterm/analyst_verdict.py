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
