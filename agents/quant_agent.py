import httpx
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel
from backend.models import TradeSignal, SignalType, PriceCandle, Trend
from core.strategies import TechnicalBreakout, MeanReversion, VolumeSurge
from configs.settings import settings
import logging

logger = logging.getLogger(__name__)

class QuantOutput(BaseModel):
    symbol: str
    signals: List[TradeSignal]
    trend: str
    nearest_support: float
    nearest_resistance: float

class QuantAgent:
    def __init__(self):
        self.base_url = f"http://localhost:{settings.SERVER_PORT}{settings.API_PREFIX}"
        self.strategies = [
            TechnicalBreakout(),
            MeanReversion(),
            VolumeSurge()
        ]

    async def analyze(self, symbol: str) -> QuantOutput:
        logger.info(f"QuantAgent: Starting analysis for {symbol}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Fetch Price History
            try:
                price_response = await client.post(
                    f"{self.base_url}/price_history",
                    json={"symbol": symbol, "period": "6mo", "interval": "1d"}
                )
                price_response.raise_for_status()
                data = price_response.json()
                candles = [PriceCandle(**c) for c in data["candles"]]
            except Exception as e:
                logger.error(f"QuantAgent Error fetching prices: {e}")
                return self._empty_output(symbol)

            if not candles:
                return self._empty_output(symbol)

            # 2. Get Technical Analysis Features (Parallel calls ideally)
            # Trend - use mode='json' to serialize datetime properly
            trend_res = await client.post(f"{self.base_url}/analysis/trend", json={"candles": [c.model_dump(mode='json') for c in candles]})
            trend_data = trend_res.json()
            
            # S/R
            sr_res = await client.post(f"{self.base_url}/analysis/support_resistance", json={"candles": [c.model_dump(mode='json') for c in candles]})
            sr_data = sr_res.json()
            
            # 3. Run Strategies
            df = pd.DataFrame([c.model_dump() for c in candles])
            signals = []
            
            for strategy in self.strategies:
                signal = strategy.analyze(df)
                if signal:
                    signals.append(signal)
            
            logger.info(f"QuantAgent: Analysis complete for {symbol}. Signals: {len(signals)}")
            return QuantOutput(
                symbol=symbol,
                signals=signals,
                trend=trend_data["trend"],
                nearest_support=sr_data["nearest_support"],
                nearest_resistance=sr_data["nearest_resistance"]
            )

    def _empty_output(self, symbol: str) -> QuantOutput:
        return QuantOutput(
            symbol=symbol,
            signals=[],
            trend="unknown",
            nearest_support=0.0,
            nearest_resistance=0.0
        )
