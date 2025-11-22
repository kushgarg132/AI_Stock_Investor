import pandas as pd
import numpy as np
from typing import List, Type
from datetime import datetime
from backend.models import BacktestResult, SignalType
from core.strategies import Strategy
from core.indicators import Indicators

class Backtester:
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital

    def run(self, df: pd.DataFrame, strategy: Strategy) -> BacktestResult:
        """
        Runs a backtest for a given strategy on the provided DataFrame.
        """
        if df.empty:
            raise ValueError("Empty DataFrame provided for backtest")
            
        # Ensure indicators
        df = Indicators.calculate_all(df)
        
        capital = self.initial_capital
        position = 0 # Shares
        trades = []
        equity_curve = [capital]
        
        # Simple loop (Vectorized is faster but logic is complex for strategies)
        # We'll iterate to simulate real-time signals
        
        # Warmup period for indicators
        warmup = 50
        
        for i in range(warmup, len(df)):
            # Slice data up to current point to simulate real-time
            # Note: This is slow for large datasets. For production, use vectorization or event-driven engine.
            # For this MVP, we'll pass the full DF but the strategy checks index -1.
            # To do this correctly without lookahead bias, we should pass df.iloc[:i+1]
            # But that's O(N^2).
            # Optimization: Strategy logic usually only needs last N rows.
            # We'll assume strategy looks at .iloc[-1] of the passed slice.
            
            current_slice = df.iloc[:i+1]
            current_bar = df.iloc[i]
            current_price = current_bar['close']
            timestamp = current_bar.name if isinstance(current_bar.name, datetime) else datetime.now() # simplistic
            
            signal = strategy.analyze(current_slice)
            
            # Execution Logic
            if signal:
                if signal.signal == SignalType.BUY and position == 0:
                    # Buy
                    shares = (capital * 0.99) / current_price # All in for simplicity or use risk sizing
                    cost = shares * current_price
                    capital -= cost
                    position = shares
                    trades.append({
                        "type": "BUY",
                        "price": current_price,
                        "timestamp": timestamp,
                        "shares": shares
                    })
                    
                elif signal.signal == SignalType.SELL and position > 0:
                    # Sell
                    revenue = position * current_price
                    capital += revenue
                    trades.append({
                        "type": "SELL",
                        "price": current_price,
                        "timestamp": timestamp,
                        "shares": position,
                        "pnl": revenue - (trades[-1]['price'] * position)
                    })
                    position = 0
            
            # Update Equity
            current_equity = capital + (position * current_price)
            equity_curve.append(current_equity)
            
        # Metrics
        equity_curve = np.array(equity_curve)
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital
        
        # Max Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        max_drawdown = drawdown.min()
        
        # Win Rate
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        closed_trades = [t for t in trades if t['type'] == 'SELL']
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0.0
        
        return BacktestResult(
            strategy_name=strategy.__class__.__name__,
            symbol=df['symbol'].iloc[0] if 'symbol' in df.columns else "UNKNOWN",
            start_date=df.index[0] if isinstance(df.index[0], datetime) else datetime.now(),
            end_date=df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now(),
            total_trades=len(closed_trades),
            win_rate=win_rate,
            profit_factor=0.0, # TODO
            total_pnl=equity_curve[-1] - self.initial_capital,
            max_drawdown=max_drawdown,
            sharpe_ratio=0.0, # TODO
            trades=trades
        )
