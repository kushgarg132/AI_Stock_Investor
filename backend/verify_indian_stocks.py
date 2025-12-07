import asyncio
import logging
import sys
import os

# Ensure project root is in path
# Ensure project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from mcp_tools.stock_info_fetcher import fetch_stock_info_logic
from mcp_tools.price_history_fetcher import fetch_price_history_logic

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IndianStockVerify")

async def verify_indian_socks():
    tickers = ["RELIANCE", "TCS", "INFY", "TATAMOTORS"]
    
    for ticker in tickers:
        logger.info(f"--- Verifying {ticker} ---")
        try:
            # Test Company Info
            info = await fetch_stock_info_logic(ticker)
            logger.info(f"SUCCESS: Found info for {ticker} -> {info.symbol} ({info.name}) | Price: {info.current_price} INR")
            
            # Test Price History
            candles, source = await fetch_price_history_logic(ticker, period="1mo")
            logger.info(f"SUCCESS: Found price history for {ticker} -> {len(candles)} candles via {source}")
            
        except Exception as e:
            logger.error(f"FAILURE for {ticker}: {e}")

if __name__ == "__main__":
    asyncio.run(verify_indian_socks())
