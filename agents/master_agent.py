from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal, SignalType, NewsArticle, FinancialEvent, PriceCandle, CompanyInfo
from .analyst_agent import AnalystAgent
from .quant_agent import QuantAgent
from .risk_agent import RiskAgent
from backend.llm import llm_service
from configs.settings import settings
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

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
    sentiment_score: float = 0.0
    impact_score: int = 0
    news_articles: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    technical_analysis: Optional[TechnicalAnalysis] = None
    all_signals: List[Dict[str, Any]] = []
    price_data: List[Dict[str, Any]] = []
    agent_confidence: float = 0.0

class MasterAgent:
    def __init__(self):
        self.analyst = AnalystAgent()
        self.quant = QuantAgent()
        self.risk = RiskAgent()
        self.base_url = f"http://localhost:{settings.SERVER_PORT}{settings.API_PREFIX}"

    async def _fetch_company_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch company information from the stock_info endpoint"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/stock_info",
                    json={"symbol": symbol}
                )
                response.raise_for_status()
                return response.json().get("company_info")
        except Exception as e:
            logger.warning(f"Failed to fetch company info for {symbol}: {e}")
            return None

    async def run(self, symbol: str, account_size: float = 100000.0, current_exposure: float = 0.0) -> MasterOutput:
        """
        Runs the full analysis pipeline.
        """
        logger.info(f"Starting Master Analysis for {symbol}...")
        
        # Run Analyst, Quant, and Company Info in parallel
        analyst_task = asyncio.create_task(self.analyst.analyze(symbol))
        quant_task = asyncio.create_task(self.quant.analyze(symbol))
        company_info_task = asyncio.create_task(self._fetch_company_info(symbol))
        
        analyst_out, quant_out, company_info = await asyncio.gather(
            analyst_task, quant_task, company_info_task
        )
        logger.info(f"Analysis complete. Sentiment: {analyst_out.sentiment_score:.2f}, Quant Signals: {len(quant_out.signals)}")
        
        # Synthesize
        # Logic: If Quant has a signal, check Analyst sentiment.
        # If Sentiment is contradictory (e.g. Buy signal but terrible news), hold or reduce size.
        # If confirmed, check Risk.
        
        best_signal = None
        decision = SignalType.HOLD
        reasoning = "No actionable signals generated. Market conditions are neutral."
        agent_confidence = 0.5  # Default neutral confidence
        
        # Simple logic: Take the first valid signal that aligns with sentiment
        for signal in quant_out.signals:
            # Sentiment Check
            if signal.signal == SignalType.BUY and analyst_out.sentiment_score < -0.2:
                reasoning = f"Quant BUY signal rejected due to negative sentiment ({analyst_out.sentiment_score:.2f})"
                logger.info(reasoning)
                continue
            if signal.signal == SignalType.SELL and analyst_out.sentiment_score > 0.2:
                reasoning = f"Quant SELL signal rejected due to positive sentiment ({analyst_out.sentiment_score:.2f})"
                logger.info(reasoning)
                continue
                
            # If we get here, sentiment is supportive or neutral
            # Risk Check
            risk_out = await self.risk.evaluate(signal, account_size, current_exposure)
            
            if risk_out.approved:
                best_signal = risk_out.adjusted_signal
                decision = best_signal.signal
                reasoning = f"Trade Approved. {best_signal.reasoning}. Sentiment: {analyst_out.sentiment_score:.2f}"
                agent_confidence = best_signal.agent_confidence
                logger.info(f"Risk Approved: {reasoning}")
                break
            else:
                reasoning = f"Trade Rejected by Risk: {risk_out.reason}"
                logger.warning(reasoning)
        
        # LLM Final Review (Optional, adds flavor)
        if best_signal:
            final_prompt = f"""
Review this trade decision:
Symbol: {symbol}
Signal: {best_signal.signal}
Reasoning: {reasoning}
Analyst Summary: {analyst_out.summary}

Provide a final 1-sentence confirmation or warning.
"""
            llm_comment = await llm_service.get_completion(final_prompt)
            reasoning += f" | LLM Comment: {llm_comment}"

        # Build technical analysis object
        technical_analysis = TechnicalAnalysis(
            trend=quant_out.trend,
            nearest_support=quant_out.nearest_support,
            nearest_resistance=quant_out.nearest_resistance
        )
        
        # Convert signals to dict for JSON serialization
        all_signals_dict = []
        for sig in quant_out.signals:
            all_signals_dict.append(sig.model_dump(mode='json'))
        
        # Convert events to dict
        events_dict = []
        for evt in analyst_out.events:
            events_dict.append(evt.model_dump(mode='json'))

        return MasterOutput(
            symbol=symbol,
            decision=decision,
            final_signal=best_signal,
            reasoning=reasoning,
            analyst_summary=analyst_out.summary,
            quant_signals_count=len(quant_out.signals),
            # Enhanced UI data
            company_info=company_info,
            sentiment_score=analyst_out.sentiment_score,
            impact_score=analyst_out.impact_score,
            news_articles=analyst_out.news_articles,
            events=events_dict,
            technical_analysis=technical_analysis,
            all_signals=all_signals_dict,
            price_data=quant_out.price_candles,
            agent_confidence=agent_confidence
        )

