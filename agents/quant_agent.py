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
    price_candles: List[Dict[str, Any]] = []  # Raw price data for charting

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
            candles_obj, source = await fetch_price_history_logic(symbol=symbol, period="6mo", interval="1d")
            # Need to act like we got response.json()
            # Previous code: candles = [PriceCandle(**c) for c in data["candles"]]
            # We have list of PriceCandle objects.
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
        # sr_response is SRResponse object
        
        # 3. Run Strategies
        df = pd.DataFrame([c.model_dump() for c in candles])
        signals = []
        
        for strategy in self.strategies:
            signal = strategy.analyze(df)
            if signal:
                signals.append(signal)
        
        logger.info(f"QuantAgent: Analysis complete for {symbol}. Signals: {len(signals)}")
        
        # Determine candles to return
        # candle_data = [c.model_dump(mode='json') for c in candles[-60:]] 
        # Debugging: returning all candles to verify data flow
        candle_data = [c.model_dump(mode='json') for c in candles]
        
        logger.info(f"QuantAgent: Returning {len(candle_data)} candles for {symbol}")
        
        return QuantOutput(
            symbol=symbol,
            signals=signals,
            trend=trend_val.value, # trend_val is Enum
            nearest_support=sr_response.nearest_support,
            nearest_resistance=sr_response.nearest_resistance,
            price_candles=candle_data
        ).model_dump(mode='json')

    def _empty_output(self, symbol: str) -> QuantOutput:
        return QuantOutput(
            symbol=symbol,
            signals=[],
            trend="unknown",
            nearest_support=0.0,
            nearest_resistance=0.0,
            price_candles=[]
        )
