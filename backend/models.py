from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Enums
class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"

class Trend(str, Enum):
    UP = "up"
    DOWN = "down"
    CHOPPY = "choppy"

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

# Models

class NewsArticle(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    title: str
    url: str
    source: str
    published_at: datetime
    content: Optional[str] = None
    sentiment: Optional[Sentiment] = None
    sentiment_score: float = 0.0  # -1.0 to 1.0
    impact_score: int = 0  # 1-10
    related_symbols: List[str] = []

class FinancialEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    event_type: str  # earnings, merger, layoff, etc.
    description: str
    date: datetime
    symbols: List[str]
    impact_rating: int

class PriceCandle(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class TradeSignal(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    signal: SignalType
    timestamp: datetime
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    position_size: Optional[float] = None
    reasoning: str
    agent_confidence: float  # 0.0 to 1.0
    source_agent: str # e.g., "MasterAgent"

class BacktestResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    total_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Dict[str, Any]] # List of individual trade details
