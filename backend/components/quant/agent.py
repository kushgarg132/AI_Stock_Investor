# import httpx - removed
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.components.shared.models import TradeSignal, SignalType, PriceCandle, Trend
from backend.components.quant.strategies import TechnicalBreakout, MeanReversion, VolumeSurge, MACDCrossover
from backend.components.quant.indicators import Indicators
from backend.configs.settings import settings
import logging

logger = logging.getLogger(__name__)


def _last(series: pd.Series) -> Optional[float]:
    """Final value of a series as a plain float, or None if it isn't a number."""
    if series.empty:
        return None
    value = series.iloc[-1]
    return float(value) if pd.notna(value) else None

class QuantOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    signals: List[TradeSignal]
    trend: str
    nearest_support: float
    nearest_resistance: float
    indicators: Dict[str, Any] = {}
    price_candles: List[Dict[str, Any]] = []  # Raw price data for charting
    market_data: Dict[str, Any] = {} # Expanded stats

from backend.components.quant.price import fetch_price_history_logic
from backend.components.quant.trend import detect_trend_logic
from backend.components.quant.support import detect_support_resistance_logic

class QuantAgent:
    def __init__(self):
        # self.base_url was removed as we use direct tool calls now
        self.strategies = [
            TechnicalBreakout(),
            MeanReversion(),
            VolumeSurge(),
            MACDCrossover()
        ]

    async def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        symbol = state['symbol']
        logger.info(f"QuantAgent: Starting analysis for {symbol}")
        
        # 1. Fetch Price History
        try:
            # Use tool logic directly
            candles_obj, source = await fetch_price_history_logic(symbol=symbol, period="1y", interval="1d") # Increased to 1y for 200 SMA
            candles = candles_obj
        except Exception as e:
            logger.error(f"QuantAgent Error fetching prices: {e}")
            return self._empty_output(symbol).model_dump(mode='json')

        if not candles:
            return self._empty_output(symbol).model_dump(mode='json')

        # 2. Get Technical Analysis Features (Parallel calls ideally)
        # Trend
        trend_val, trend_details = detect_trend_logic(candles)
        
        # S/R
        sr_response = detect_support_resistance_logic(candles)
        
        # Calculate Indicators
        df = pd.DataFrame([c.model_dump() for c in candles])
        indicators = self._calculate_indicators(df)
        
        # Calculate Basic Stats (High/Low/Avg)
        current_price = df['close'].iloc[-1]
        market_data = {
            "current_price": current_price,
            "day_high": df['high'].iloc[-1],
            "day_low": df['low'].iloc[-1],
            "day_open": df['open'].iloc[-1],
            "prev_close": df['close'].iloc[-2] if len(df) > 1 else current_price,
            "volume_avg_20": float(df['volume'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else 0,
            "period_high_6m": float(df['high'].max()),
            "period_low_6m": float(df['low'].min()),
        }

        # 3. Run Strategies
        signals = []
        
        for strategy in self.strategies:
            signal = strategy.analyze(df)
            if signal:
                signals.append(signal)
        
        # Sort by confidence (descending) and take top 3
        signals.sort(key=lambda x: x.conviction, reverse=True)
        signals = signals[:3]
        
        logger.info(f"QuantAgent: Analysis complete for {symbol}. Signals: {len(signals)}")
        
        # Determine candles to return
        candle_data = [c.model_dump(mode='json') for c in candles]
        
        logger.info(f"QuantAgent: Returning {len(candle_data)} candles for {symbol}")
        
        return QuantOutput(
            symbol=symbol,
            signals=signals,
            trend=trend_val.value, # trend_val is Enum
            nearest_support=sr_response.nearest_support,
            nearest_resistance=sr_response.nearest_resistance,
            indicators=indicators,
            market_data=market_data,
            price_candles=candle_data
        ).model_dump(mode='json')

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Latest value of each indicator, for UI display."""
        try:
            if df.empty:
                return {}

            close = df['close']
            macd_line, signal_line, histogram = Indicators.macd(close)
            bb_upper, bb_lower = Indicators.bollinger_bands(close)
            sma_20 = _last(Indicators.sma(close, 20))

            return {
                "rsi": _last(Indicators.rsi(close)),
                "macd": {
                    "line": _last(macd_line),
                    "signal": _last(signal_line),
                    "histogram": _last(histogram),
                },
                "bb_upper": _last(bb_upper),
                "bb_lower": _last(bb_lower),
                "bb_middle": sma_20,
                "sma_20": sma_20,
                "sma_50": _last(Indicators.sma(close, 50)),
                "sma_200": _last(Indicators.sma(close, 200)),
                "ema_20": _last(Indicators.ema(close, 20)),
                "atr": _last(Indicators.atr(df['high'], df['low'], close)),
            }
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}

    def _empty_output(self, symbol: str) -> QuantOutput:
        return QuantOutput(
            symbol=symbol,
            signals=[],
            trend="unknown",
            nearest_support=0.0,
            nearest_resistance=0.0,
            indicators={},
            price_candles=[],
            market_data={}
        )
