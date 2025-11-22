import asyncio
import httpx
from agents.master_agent import MasterAgent

async def verify_api():
    print("Checking API Health...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://localhost:8000/")
            print(f"API Status: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"API Check Failed: {e}")
            return False
    return True

async def run_agent_test():
    print("\nRunning Master Agent Test for AAPL...")
    agent = MasterAgent()
    try:
        result = await agent.run("AAPL")
        print(f"\nDecision: {result.decision}")
        print(f"Reasoning: {result.reasoning}")
        print(f"Analyst Summary: {result.analyst_summary}")
        print(f"Quant Signals: {result.quant_signals_count}")
        if result.final_signal:
            print(f"Trade Details: {result.final_signal}")
    except Exception as e:
        print(f"Agent Test Failed: {e}")

async def main():
    if await verify_api():
        await run_agent_test()
    else:
        print("Skipping Agent Test due to API failure. Make sure server is running.")

if __name__ == "__main__":
    asyncio.run(main())
