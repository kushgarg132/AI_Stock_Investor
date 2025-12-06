from typing import Dict, List
import logging
import json
from backend.llm import llm_service

logger = logging.getLogger(__name__)

async def resolve_company_query(query: str) -> Dict:
    """
    Resolves a user query (ticker or company name) to a valid stock ticker 
    and finds similar peer companies.
    
    Returns:
        {
            "symbol": "AAPL",
            "peers": ["MSFT", "GOOGL", "AMZN"],
            "name": "Apple Inc."
        }
    """
    
    # Fallback mapping for common queries when LLM is rate-limited
    FALLBACK_MAPPING = {
        "APPLE": {"symbol": "AAPL", "name": "Apple Inc.", "peers": ["MSFT", "GOOGL", "AMZN", "META"]},
        "TESLA": {"symbol": "TSLA", "name": "Tesla Inc.", "peers": ["RIVN", "F", "GM", "LCID"]},
        "MICROSOFT": {"symbol": "MSFT", "name": "Microsoft Corp.", "peers": ["AAPL", "GOOGL", "AMZN", "ORCL"]},
        "NVIDIA": {"symbol": "NVDA", "name": "NVIDIA Corp.", "peers": ["AMD", "INTC", "TSM", "QCOM"]},
        "GOOGLE": {"symbol": "GOOGL", "name": "Alphabet Inc.", "peers": ["MSFT", "AMZN", "META", "AAPL"]},
    }
    
    # Prompt for the LLM
    prompt = f"""
    You are a financial data assistant. Verify the user input.
    Input: "{query}"

    1. Identify the primary US or major international stock ticker for this input. 
       - If it's already a ticker (like "AAPL"), use it.
       - If it's a company name (like "Apple"), find the ticker ("AAPL").
       - If it's invalid or not a public company, return "UNKNOWN".
       
    2. Identify up to 5 similar peer company tickers (competitors or same sector).

    3. Return ONLY valid JSON in this format:
    {{
        "symbol": "TICKER",
        "name": "Company Name",
        "peers": ["PEER1", "PEER2", "PEER3"]
    }}
    
    If UNKNOWN, return:
    {{
        "symbol": "UNKNOWN",
        "name": "",
        "peers": []
    }}
    """
    
    try:
        response_text = await llm_service.get_completion(prompt, system_prompt="You are a strict JSON output generator.")
        
        # Clean response if it contains markdown code blocks
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(clean_text)
        
        if data.get("symbol") == "UNKNOWN":
            logger.warning(f"Could not resolve query: {query}")
            return {"symbol": query.upper(), "peers": [], "name": query} # Fallback to original query
            
        return data
        
    except Exception as e:
        logger.warning(f"Error resolving query {query} with LLM: {e}")
        
        # Check fallback
        upper_q = query.upper()
        if upper_q in FALLBACK_MAPPING:
             logger.info(f"Using fallback for {query}")
             return FALLBACK_MAPPING[upper_q]
             
        # Fallback
        return {"symbol": query.upper(), "peers": [], "name": query}
