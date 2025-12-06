import pandas as pd
from typing import List, Optional
from datetime import datetime
import logging

from backend.models import TradeSignal, SignalType
from .indicators import Indicators
from .support_resistance import SupportResistance
from .trend import TrendDetector, Trend

logger = logging.getLogger(__name__)

class Strategy:
    def analyze(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        raise NotImplementedError

class TechnicalBreakout(Strategy):
    def analyze(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        if len(df) < 50:
            return None
            
        # Ensure indicators are present
        if 'sma_50' not in df.columns:
            df = Indicators.calculate_all(df)
            
        current_price = df['close'].iloc[-1]
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else "UNKNOWN"
        
        # Detect S/R levels
        levels = SupportResistance.identify_levels(df)
        support, resistance = SupportResistance.get_nearest_levels(current_price, levels)
        
        # Breakout Logic: Close above resistance with volume confirmation
        # Simple check: if previous close was below resistance and current is above
        prev_close = df['close'].iloc[-2]
        
        if resistance and prev_close < resistance and current_price > resistance:
            # Volume check: Current volume > 1.5 * Avg Volume
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            if df['volume'].iloc[-1] > 1.5 * avg_vol:
                return TradeSignal(
                    symbol=symbol,
                    signal=SignalType.BUY,
                    timestamp=datetime.now(),
                    entry_price=current_price,
                    stop_loss=resistance * 0.98, # Stop below the breakout level
                    target_price=current_price + (current_price - resistance) * 2, # 2R target
                    reasoning=f"Breakout above resistance {resistance:.2f} with volume surge",
                    agent_confidence=0.8,
                    source_agent="QuantAgent"
                )
        return None

class MeanReversion(Strategy):
    def analyze(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        if len(df) < 50:
            return None
        
        if 'rsi_14' not in df.columns:
            df = Indicators.calculate_all(df)
            
        current_price = df['close'].iloc[-1]
        rsi = df['rsi_14'].iloc[-1]
        lower_band = df['bb_lower'].iloc[-1]
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else "UNKNOWN"
        
        # Buy Condition: RSI < 30 AND Price < Lower Bollinger Band
        if rsi < 30 and current_price < lower_band:
             return TradeSignal(
                symbol=symbol,
                signal=SignalType.BUY,
                timestamp=datetime.now(),
                entry_price=current_price,
                stop_loss=current_price * 0.95,
                target_price=df['sma_20'].iloc[-1] if 'sma_20' in df.columns else current_price * 1.05,
                reasoning=f"Oversold: RSI {rsi:.2f} and Price below Lower BB",
                agent_confidence=0.7,
                source_agent="QuantAgent"
            )
        return None

class VolumeSurge(Strategy):
    def analyze(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        if len(df) < 50:
            return None
            
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        current_vol = df['volume'].iloc[-1]
        current_price = df['close'].iloc[-1]
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else "UNKNOWN"
        
        if current_vol > 3 * avg_vol: # Massive volume spike
             # Direction?
            if df['close'].iloc[-1] > df['open'].iloc[-1]:
                signal = SignalType.BUY
                reason = "Massive buying volume"
            else:
                signal = SignalType.SELL
                reason = "Massive selling volume"
                
            return TradeSignal(
                symbol=symbol,
                signal=signal,
                timestamp=datetime.now(),
                entry_price=current_price,
                stop_loss=current_price * 0.98 if signal == SignalType.BUY else current_price * 1.02,
                target_price=current_price * 1.05 if signal == SignalType.BUY else current_price * 0.95,
                reasoning=f"{reason}: {current_vol:.0f} vs Avg {avg_vol:.0f}",
                agent_confidence=0.6, # Lower confidence as it's just volume
                source_agent="QuantAgent"
            )
        return None

class MACDCrossover(Strategy):
    def analyze(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        if len(df) < 30:
            return None
            
        if 'macd_line' not in df.columns:
            df = Indicators.calculate_all(df)
            
        current_price = df['close'].iloc[-1]
        symbol = df['symbol'].iloc[-1] if 'symbol' in df.columns else "UNKNOWN"
        
        # MACD Logic
        curr_hist = df['macd_hist'].iloc[-1]
        prev_hist = df['macd_hist'].iloc[-2]
        
        # Bullish Crossover (Histogram flips from negative to positive)
        if prev_hist < 0 and curr_hist > 0:
            return TradeSignal(
                symbol=symbol,
                signal=SignalType.BUY,
                timestamp=datetime.now(),
                entry_price=current_price,
                stop_loss=current_price * 0.97,
                target_price=current_price * 1.06,
                reasoning=f"MACD Bullish Crossover",
                agent_confidence=0.75,
                source_agent="QuantAgent"
            )
            
        # Bearish Crossover (Histogram flips from positive to negative)
        if prev_hist > 0 and curr_hist < 0:
            return TradeSignal(
                symbol=symbol,
                signal=SignalType.SELL,
                timestamp=datetime.now(),
                entry_price=current_price,
                stop_loss=current_price * 1.03,
                target_price=current_price * 0.94,
                reasoning=f"MACD Bearish Crossover",
                agent_confidence=0.75,
                source_agent="QuantAgent"
            )
            
        return None
