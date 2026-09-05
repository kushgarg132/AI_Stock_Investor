"""Ported from backend/components/quant/strategies.py::MACDCrossover. Same
logic and thresholds -- structural port, not a redesign."""

from backend.components.quant.indicators import Indicators
from backend.core.models import Intent, Side
from backend.engine.protocols import StrategySpec
from backend.strategies.base import TokenResolvingStrategy, bars_to_dataframe


class MACDCrossoverStrategy(TokenResolvingStrategy):
    def __init__(self, universe: list[str], symbol_for_token: dict[int, str]) -> None:
        super().__init__(universe, symbol_for_token)
        self.spec = StrategySpec(
            name="macd_crossover", mode="LONGTERM", timeframe="1d",
            warmup_bars=30, universe=universe,
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
        curr_hist = df["macd_hist"].iloc[-1]
        prev_hist = df["macd_hist"].iloc[-2]

        if prev_hist < 0 and curr_hist > 0:
            ctx.submit(Intent(
                symbol=symbol, side=Side.BUY, strength=0.75,
                reason_codes=["macd_bullish_crossover"],
                stop_hint=current_price * 0.97,
                target_hint=current_price * 1.06,
            ))
        elif prev_hist > 0 and curr_hist < 0:
            ctx.submit(Intent(
                symbol=symbol, side=Side.SELL, strength=0.75,
                reason_codes=["macd_bearish_crossover"],
                stop_hint=current_price * 1.03,
                target_hint=current_price * 0.94,
            ))
