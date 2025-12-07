from typing import List, Optional, Any, Dict, TypedDict, Annotated
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal, SignalType, NewsArticle, FinancialEvent, PriceCandle, CompanyInfo
from .analyst_agent import AnalystAgent
from .quant_agent import QuantAgent
from .risk_agent import RiskAgent
from backend.llm import llm_service
from backend.configs.settings import settings
# import httpx - removed
import asyncio
import logging
import operator
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

from backend.agents.search_tool import resolve_company_query
from backend.core.memory import memory_manager

logger = logging.getLogger(__name__)

# --- Data Models (Keep as is for API compatibility) ---
class TechnicalAnalysis(BaseModel):
    """Technical analysis data from QuantAgent"""
    model_config = ConfigDict(use_enum_values=True)
    
    trend: str
    nearest_support: float
    nearest_resistance: float

class MasterOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    decision: SignalType
    final_signal: Optional[TradeSignal] = None
    reasoning: str
    analyst_summary: str
    quant_signals_count: int
    
    # Enhanced data for UI
    company_info: Optional[Dict[str, Any]] = None
    
    # Sentiment
    sentiment_score: float = 0.0
    impact_score: int = 0
    sentiment: Dict[str, Any] = {} # New structural field
    
    # News & Events
    news_articles: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    
    # Technicals
    technical_analysis: Optional[TechnicalAnalysis] = None
    all_signals: List[Dict[str, Any]] = []
    price_data: List[Dict[str, Any]] = []
    indicators: Dict[str, Any] = {} # New field
    market_data: Dict[str, Any] = {} # New field
    
    # Risk
    risk: Dict[str, Any] = {} # New field
    
    agent_confidence: float = 0.0
    logs: List[str] = []
    peers: List[str] = []
class AgentState(TypedDict):
    symbol: str
    account_size: float
    current_exposure: float
    
    # Outputs
    analyst_output: Optional[Dict[str, Any]]
    quant_output: Optional[Dict[str, Any]]
    risk_output: Optional[Dict[str, Any]]
    company_info: Optional[Dict[str, Any]]
    peers: List[str]
    
    # Final Decision Data
    decision: SignalType
    reasoning: str
    final_signal: Optional[Dict[str, Any]]
    
    messages: Annotated[List[BaseMessage], operator.add]
    past_memories: List[Dict[str, Any]]

# --- Master Agent ---
class MasterAgent:
    def __init__(self):
        self.analyst = AnalystAgent()
        self.quant = QuantAgent()
        self.risk = RiskAgent()
        
        # Build Graph
        workflow = StateGraph(AgentState)
        
        # Add Nodes
        workflow.add_node("resolve_query", self.resolve_node)
        workflow.add_node("start_analysis", self.start_node)
        workflow.add_node("analyst", self.analyst_node)
        workflow.add_node("quant", self.quant_node)
        workflow.add_node("company_info", self.company_info_node)
        workflow.add_node("risk_assessment", self.risk_node)
        workflow.add_node("decision_maker", self.decision_node)
        
        # Define Edges (Sequential Flow to ensure all data is ready)
        workflow.set_entry_point("resolve_query")
        
        workflow.add_edge("resolve_query", "start_analysis")
        workflow.add_edge("start_analysis", "company_info")
        workflow.add_edge("company_info", "analyst")
        workflow.add_edge("analyst", "quant")
        workflow.add_edge("quant", "risk_assessment")
        workflow.add_edge("risk_assessment", "decision_maker")
        workflow.add_edge("decision_maker", END)
        
        self.graph = workflow.compile()

    # --- Nodes ---
    async def resolve_node(self, state: AgentState):
        query = state['symbol']
        logger.info(f"Resolving query: {query}")
        resolved_data = await resolve_company_query(query)
        
        logger.info(f"Resolved to: {resolved_data}")
        
        return {
            "symbol": resolved_data['symbol'], 
            "peers": resolved_data.get('peers', []),
            "messages": [HumanMessage(content=f"Resolved '{query}' to {resolved_data['symbol']}")]
        }

    async def start_node(self, state: AgentState):
        logger.info(f"Starting analysis for {state['symbol']}")
        # formatted_memories = [] # Could format this for the prompt later
        memories = await memory_manager.get_memories(state['symbol'], limit=3)
        if memories:
            logger.info(f"Found {len(memories)} past memories for {state['symbol']}")
            
        return {
            "messages": [HumanMessage(content=f"Analysis started for {state['symbol']}")],
            "past_memories": memories
        }

    async def analyst_node(self, state: AgentState):
        result = await self.analyst.analyze(state) # Modified to accept state
        return {"analyst_output": result, "messages": [HumanMessage(content="Analyst finished")]}

    async def quant_node(self, state: AgentState):
        result = await self.quant.analyze(state) # Modified to accept state
        candle_count = len(result.get('price_candles', []))
        return {"quant_output": result, "messages": [HumanMessage(content=f"Quant finished. Processed {candle_count} price candles.")]}

    async def company_info_node(self, state: AgentState):
        logger.info("Fetching company info...")
        # Keeping internal logic here or could move to an agent
        try:
            from backend.mcp_tools.stock_info_fetcher import fetch_stock_info_logic
            info_obj = await fetch_stock_info_logic(state['symbol'])
            # info_obj is CompanyInfo model
            return {"company_info": info_obj.model_dump(mode='json')}
        except Exception as e:
            logger.warning(f"Failed to fetch company info: {e}")
            return {"company_info": None}

    async def risk_node(self, state: AgentState):
        # Risk Agent now orchestrates Sentiment Check + Risk Check
        result = await self.risk.evaluate(state)
        return {"risk_output": result}

    async def decision_node(self, state: AgentState):
        # Final packaging
        risk_out = state.get("risk_output")
        analyst_out = state.get("analyst_output")
        quant_out = state.get("quant_output")
        company = state.get("company_info")
        
        if not risk_out or not analyst_out or not quant_out:
             # Should not happen if graph flows correctly
             return {"decision": SignalType.HOLD, "reasoning": "Incomplete analysis"}
        
        # LLM Flavor text
        reasoning = risk_out.get('reason', "No decision made")
        decision = risk_out.get('approved') and risk_out.get('adjusted_signal', {}).get('signal') or SignalType.HOLD
        
        if decision != SignalType.HOLD:
             final_prompt = f"Review trade: {state['symbol']} {decision}. Reason: {reasoning}. Analyst: {analyst_out.get('summary')}. One sentence comment."
             llm_comment = await llm_service.get_completion(final_prompt)
             reasoning += f" | LLM: {llm_comment}"

        tech_data = TechnicalAnalysis(
            trend=quant_out['trend'],
            nearest_support=quant_out['nearest_support'],
            nearest_resistance=quant_out['nearest_resistance']
        )
        
        # Construct output dicts
        
        # Save to memory
        await memory_manager.add_memory(
            symbol=state['symbol'],
            content=reasoning,
            decision=decision,
            memory_type="full_analysis"
        )
        
        return {
            "decision": decision,
            "reasoning": reasoning,
            "final_signal": risk_out.get('adjusted_signal'),
            "messages": [HumanMessage(content="Decision Made")]
        }

    async def run(self, symbol: str, account_size: float = 100000.0, current_exposure: float = 0.0) -> MasterOutput:
        inputs = {
            "symbol": symbol,
            "account_size": account_size,
            "current_exposure": current_exposure,
            "analyst_output": None,
            "quant_output": None,
            "risk_output": None,
            "company_info": None,
            "peers": [],
            "decision": SignalType.HOLD,
            "reasoning": "",
            "messages": [HumanMessage(content=f"Input: {symbol}")],
            "past_memories": []
        }
        
        # Run graph
        result = await self.graph.ainvoke(inputs)
        
        # Parse result back to MasterOutput
        quant_out = result['quant_output']
        analyst_out = result['analyst_output']
        
        return MasterOutput(
            symbol=result['symbol'], # Use resolved symbol
            decision=result['decision'] or SignalType.HOLD,
            final_signal=result['final_signal'],
            reasoning=result['reasoning'],
            analyst_summary=analyst_out['summary'],
            quant_signals_count=len(quant_out['signals']),
            company_info=result.get('company_info'),
            sentiment_score=analyst_out['sentiment_score'],
            impact_score=analyst_out['impact_score'],
            sentiment=analyst_out.get('sentiment_analysis', {}),
            news_articles=analyst_out['news_articles'],
            events=analyst_out['events'],
            technical_analysis=TechnicalAnalysis(
                trend=quant_out['trend'],
                nearest_support=quant_out['nearest_support'],
                nearest_resistance=quant_out['nearest_resistance']
            ),
            all_signals=quant_out['signals'],
            price_data=quant_out['price_candles'],
            indicators=quant_out.get('indicators', {}),
            market_data=quant_out.get('market_data', {}),
            risk=result.get('risk_output', {}).get('risk_analysis', {}),
            agent_confidence=0.8,
            logs=[m.content for m in result['messages']],
            peers=result.get('peers', [])
        )

