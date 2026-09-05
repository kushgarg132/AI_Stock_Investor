"""Ported from backend/components/quant/strategies.py::MeanReversion. Same
logic and thresholds -- structural port, not a redesign.

Note: the original's target formula checked for a `sma_20` column that
`Indicators.calculate_all` never actually populates (it only adds sma_50/
sma_200), so that branch was always dead code and the target always fell
back to `current_price * 1.05`. Ported as the fallback directly rather than
carrying forward a check that can never be true.
"""

from backend.components.quant.indicators import Indicators
from backend.core.models import Intent, Side
from backend.engine.protocols import StrategySpec
from backend.strategies.base import TokenResolvingStrategy, bars_to_dataframe


class MeanReversionStrategy(TokenResolvingStrategy):
    def __init__(self, universe: list[str], symbol_for_token: dict[int, str]) -> None:
        super().__init__(universe, symbol_for_token)
        self.spec = StrategySpec(
            name="mean_reversion", mode="LONGTERM", timeframe="1d",
            warmup_bars=50, universe=universe,
        )

    def on_bar(self, ctx, bar) -> None:
        symbol = self.symbol_for(bar)
        if symbol is None:
            return

        history = ctx.history(symbol, self.spec.warmup_bars)
        if len(history) < self.spec.warmup_bars:
            return

        df = Indicators.calculate_all(bars_to_dataframe(history))
        current_price = df["close"].iloc[-1]
        rsi = df["rsi_14"].iloc[-1]
        lower_band = df["bb_lower"].iloc[-1]

        # Buy condition: RSI oversold AND price below the lower Bollinger band.
        if not (rsi < 30 and current_price < lower_band):
            return

        ctx.submit(Intent(
            symbol=symbol, side=Side.BUY, strength=0.7,
            reason_codes=["oversold_rsi_below_lower_band"],
            stop_hint=current_price * 0.95,
            target_hint=current_price * 1.05,
        ))
