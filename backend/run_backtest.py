import asyncio
import pandas as pd
from backend.core.backtester import Backtester
from backend.core.strategies import TechnicalBreakout
from backend.mcp_tools.price_history_fetcher import fetch_price_history_logic, PriceHistoryRequest # Direct import for script
# Note: Direct import of fetcher logic might require refactoring if it depends on request context, 
# but here we'll just use yfinance directly or mock it for the script to be standalone-ish.
import yfinance as yf
from backend.models import PriceCandle

def get_data(symbol):
    print(f"Fetching data for {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1y", interval="1d")
    # Rename columns to lowercase
    df.columns = [c.lower() for c in df.columns]
    df['symbol'] = symbol
    return df

def run_backtest():
    df = get_data("AAPL")
    if df.empty:
        print("No data fetched.")
        return

    print("Running Backtest...")
    strategy = TechnicalBreakout()
    backtester = Backtester(initial_capital=100000)
    
    result = backtester.run(df, strategy)
    
    print("\nBacktest Results:")
    print(f"Strategy: {result.strategy_name}")
    print(f"Total Trades: {result.total_trades}")
    print(f"Win Rate: {result.win_rate:.2%}")
    print(f"Total PnL: ${result.total_pnl:.2f}")
    print(f"Max Drawdown: {result.max_drawdown:.2%}")
    
    if result.trades:
        print("\nLast 5 Trades:")
        for t in result.trades[-5:]:
            print(t)

if __name__ == "__main__":
    run_backtest()
