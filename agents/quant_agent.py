# import httpx - removed
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal, SignalType, PriceCandle, Trend
from core.strategies import TechnicalBreakout, MeanReversion, VolumeSurge, MACDCrossover
from configs.settings import settings
import logging

logger = logging.getLogger(__name__)

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

from mcp_tools.price_history_fetcher import fetch_price_history_logic
from mcp_tools.trend_detector import detect_trend_logic
from mcp_tools.support_resistance_detector import detect_support_resistance_logic

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
        """Calculates RSI, MACD, Bollinger Bands, ATR, SMA, EMA"""
        try:
            if df.empty:
                return {}
                
            close = df['close']
            high = df['high']
            low = df['low']
            
            # Simple Moving Averages
            sma_20 = close.rolling(window=20).mean().iloc[-1]
            sma_50 = close.rolling(window=50).mean().iloc[-1]
            sma_200 = close.rolling(window=200).mean().iloc[-1]
            
            # EMA
            ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
            
            # RSI (14)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean() # Simple avg for gain/loss often used in simple logic, but Wilder uses EMA
            # Using simple rolling for stability in small datasets, or EWM
            # Better standard RSI:
            udp = delta.where(delta > 0, 0)
            ddn = -delta.where(delta < 0, 0)
            avg_gain = udp.ewm(com=13, adjust=False).mean() # com=13 -> span=27, alpha=1/14
            avg_loss = ddn.ewm(com=13, adjust=False).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # MACD (12, 26, 9)
            exp1 = close.ewm(span=12, adjust=False).mean()
            exp2 = close.ewm(span=26, adjust=False).mean()
            macd_line = exp1 - exp2
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            
            # Bollinger Bands (20, 2)
            bb_sma = close.rolling(window=20).mean()
            bb_std = close.rolling(window=20).std()
            bb_upper = bb_sma + (bb_std * 2)
            bb_lower = bb_sma - (bb_std * 2)
            
            # ATR (14)
            # TR = max(H-L, |H-Cp|, |L-Cp|)
            prev_close = close.shift(1)
            tr1 = high - low
            tr2 = (high - prev_close).abs()
            tr3 = (low - prev_close).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            return {
                "rsi": float(current_rsi) if pd.notna(current_rsi) else None,
                "macd": {
                    "line": float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None,
                    "signal": float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else None,
                    "histogram": float(histogram.iloc[-1]) if pd.notna(histogram.iloc[-1]) else None
                },
                "bb_upper": float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else None,
                "bb_lower": float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else None,
                "bb_middle": float(bb_sma.iloc[-1]) if pd.notna(bb_sma.iloc[-1]) else None,
                "sma_20": float(sma_20) if pd.notna(sma_20) else None,
                "sma_50": float(sma_50) if pd.notna(sma_50) else None,
                "sma_200": float(sma_200) if pd.notna(sma_200) else None,
                "ema_20": float(ema_20) if pd.notna(ema_20) else None,
                "atr": float(atr) if pd.notna(atr) else None
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
