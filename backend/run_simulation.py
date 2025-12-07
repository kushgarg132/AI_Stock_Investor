import asyncio
import sys
import os
import logging

# Add current directory to path so we can import modules
sys.path.append(os.getcwd())

from backend.configs.logging_config import setup_logging
from backend.agents.master_agent import MasterAgent
from backend.models import SignalType

# Initialize logging
logger = setup_logging()

async def run_simulation():
    print("Starting AI Stock Investor Simulation...")
    print("----------------------------------------")
    
    # Configuration
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMD"]
    budget = 5.0 # $5 budget
    
    print(f"Budget: ${budget}")
    print(f"Symbols: {', '.join(symbols)}")
    print("----------------------------------------")
    
    agent = MasterAgent()
    
    results = []
    
    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")
        try:
            # Run Master Agent
            # Note: We pass the full budget as account_size, assuming we want to use it all for one trade if possible,
            # or we can treat it as the total portfolio value.
            # For this simulation, let's say we have $5 total and want to see if we can buy anything.
            output = await agent.run(symbol, account_size=budget)
            
            print(f"Decision: {output.decision.value.upper()}")
            print(f"Reasoning: {output.reasoning}")
            
            if output.final_signal:
                print(f"Signal Details:")
                print(f"  Action: {output.final_signal.signal}")
                print(f"  Entry Price: ${output.final_signal.entry_price:.2f}")
                print(f"  Stop Loss: ${output.final_signal.stop_loss:.2f}")
                print(f"  Position Size (Shares): {output.final_signal.position_size:.4f}")
                cost = output.final_signal.entry_price * output.final_signal.position_size
                print(f"  Estimated Cost: ${cost:.2f}")
            
            results.append(output)
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            import traceback
            traceback.print_exc()
            
    print("\n----------------------------------------")
    print("Simulation Complete.")
    print("Summary:")
    for res in results:
        print(f"{res.symbol}: {res.decision.value} - {res.reasoning[:50]}...")

if __name__ == "__main__":
    asyncio.run(run_simulation())
