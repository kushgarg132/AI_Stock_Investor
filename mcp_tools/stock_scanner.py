"""
Stock Scanner - Scans Indian stocks for bullish signals.
Finds stocks likely to go up in the next week based on technical analysis.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import asyncio

import yfinance as yf
import pandas as pd
import numpy as np

from core.indian_stocks import HIGH_VOLATILITY_PICKS, get_stock_symbol_nse

logger = logging.getLogger(__name__)
router = APIRouter()


class StockSignal(BaseModel):
    symbol: str
    name: str
    current_price: float
    change_percent: float
    signal_strength: int  # 1-5 stars
    signal_type: str  # "bullish", "bearish", "neutral"
    reasons: List[str]
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence: float  # 0-100%


class ScannerResponse(BaseModel):
    scan_time: str
    stocks_scanned: int
    bullish_picks: List[StockSignal]
    message: str


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    if loss.iloc[-1] == 0:
        return 100.0
    
    rs = gain.iloc[-1] / loss.iloc[-1]
    return 100 - (100 / (1 + rs))


def calculate_sma(prices: pd.Series, period: int) -> float:
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean().iloc[-1]


def analyze_stock(symbol: str) -> Optional[StockSignal]:
    """Analyze a single stock for bullish signals"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get 1 month of daily data
        df = ticker.history(period="1mo", interval="1d")
        
        if df.empty or len(df) < 14:
            return None
        
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
        change_percent = ((current_price - prev_price) / prev_price) * 100
        
        # Calculate indicators
        rsi = calculate_rsi(df['Close'])
        sma_20 = calculate_sma(df['Close'], 20) if len(df) >= 20 else calculate_sma(df['Close'], len(df))
        sma_5 = calculate_sma(df['Close'], 5)
        
        avg_volume = df['Volume'].mean()
        today_volume = df['Volume'].iloc[-1]
        volume_surge = today_volume / avg_volume if avg_volume > 0 else 1
        
        # Score bullish signals
        reasons = []
        signal_strength = 0
        
        # RSI oversold bounce
        if rsi < 40:
            reasons.append(f"RSI oversold at {rsi:.1f}")
            signal_strength += 1
        
        # Price above SMA 20
        if current_price > sma_20:
            reasons.append(f"Price above 20-day SMA")
            signal_strength += 1
        
        # Short-term momentum (5-day SMA rising)
        if sma_5 > sma_20 * 0.98:  # 5-day close to or above 20-day
            reasons.append("Short-term momentum positive")
            signal_strength += 1
        
        # Volume surge
        if volume_surge > 1.5:
            reasons.append(f"Volume surge: {volume_surge:.1f}x average")
            signal_strength += 1
        
        # Recent price increase
        week_ago_price = df['Close'].iloc[-5] if len(df) >= 5 else df['Close'].iloc[0]
        week_change = ((current_price - week_ago_price) / week_ago_price) * 100
        if week_change > 3:
            reasons.append(f"Up {week_change:.1f}% this week")
            signal_strength += 1
        
        # Only return if at least 2 bullish signals
        if signal_strength < 2:
            return None
        
        # Calculate targets
        target_price = current_price * 1.05  # 5% target
        stop_loss = current_price * 0.97  # 3% stop loss
        
        # Clean symbol name
        clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
        
        return StockSignal(
            symbol=symbol,
            name=clean_symbol,
            current_price=round(current_price, 2),
            change_percent=round(change_percent, 2),
            signal_strength=min(signal_strength, 5),
            signal_type="bullish",
            reasons=reasons,
            target_price=round(target_price, 2),
            stop_loss=round(stop_loss, 2),
            confidence=min(signal_strength * 20, 100)
        )
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None


@router.get("/scanner/bullish", response_model=ScannerResponse)
async def scan_for_bullish_stocks():
    """
    Scan small/mid cap Indian stocks for bullish signals.
    Returns stocks likely to go up in the next week.
    """
    logger.info("Starting bullish stock scan...")
    
    symbols = [get_stock_symbol_nse(s) for s in HIGH_VOLATILITY_PICKS]
    bullish_picks = []
    
    for symbol in symbols:
        logger.info(f"Scanning {symbol}...")
        signal = analyze_stock(symbol)
        if signal:
            bullish_picks.append(signal)
    
    # Sort by signal strength
    bullish_picks.sort(key=lambda x: x.signal_strength, reverse=True)
    
    logger.info(f"Scan complete. Found {len(bullish_picks)} bullish stocks.")
    
    return ScannerResponse(
        scan_time=datetime.now().isoformat(),
        stocks_scanned=len(symbols),
        bullish_picks=bullish_picks,
        message=f"Found {len(bullish_picks)} bullish stocks out of {len(symbols)} scanned"
    )


@router.get("/scanner/test")
async def test_scanner():
    """Quick test endpoint"""
    symbol = "SUZLON.NS"
    signal = analyze_stock(symbol)
    if signal:
        return signal.model_dump()
    return {"message": f"No bullish signal for {symbol}"}
