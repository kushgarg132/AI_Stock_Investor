from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal, SignalType
from .analyst_agent import AnalystAgent
from .quant_agent import QuantAgent
from .risk_agent import RiskAgent
from backend.llm import llm_service
import asyncio
import logging

logger = logging.getLogger(__name__)

class MasterOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    decision: SignalType
    final_signal: Optional[TradeSignal]
    reasoning: str
    analyst_summary: str
    quant_signals_count: int

class MasterAgent:
    def __init__(self):
        self.analyst = AnalystAgent()
        self.quant = QuantAgent()
        self.risk = RiskAgent()

    async def run(self, symbol: str, account_size: float = 100000.0, current_exposure: float = 0.0) -> MasterOutput:
        """
        Runs the full analysis pipeline.
        """
        logger.info(f"Starting Master Analysis for {symbol}...")
        
        # Run Analyst and Quant in parallel
        analyst_task = asyncio.create_task(self.analyst.analyze(symbol))
        quant_task = asyncio.create_task(self.quant.analyze(symbol))
        
        analyst_out, quant_out = await asyncio.gather(analyst_task, quant_task)
        logger.info(f"Analysis complete. Sentiment: {analyst_out.sentiment_score:.2f}, Quant Signals: {len(quant_out.signals)}")
        
        # Synthesize
        # Logic: If Quant has a signal, check Analyst sentiment.
        # If Sentiment is contradictory (e.g. Buy signal but terrible news), hold or reduce size.
        # If confirmed, check Risk.
        
        best_signal = None
        decision = SignalType.HOLD
        reasoning = "No signals generated."
        
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

        return MasterOutput(
            symbol=symbol,
            decision=decision,
            final_signal=best_signal,
            reasoning=reasoning,
            analyst_summary=analyst_out.summary,
            quant_signals_count=len(quant_out.signals)
        )
