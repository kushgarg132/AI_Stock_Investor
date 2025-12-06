# import httpx - removed
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal
from configs.settings import settings
import logging
from mcp_tools.risk_rules_tool import check_risk_logic
import pandas as pd
from core.indicators import Indicators

logger = logging.getLogger(__name__)

class RiskOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    approved: bool
    adjusted_signal: Optional[TradeSignal]
    reason: str

class RiskAgent:
    def __init__(self):
        pass
        # self.base_url removed
        
    async def evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates trades based on Quant signals, Analyst sentiment, and Risk rules.
        """
        symbol = state['symbol']
        account_size = state['account_size']
        current_exposure = state['current_exposure']
        
        quant_out = state.get('quant_output')
        analyst_out = state.get('analyst_output')
        
        if not quant_out or not analyst_out:
             return RiskOutput(
                 approved=False, 
                 adjusted_signal=None, 
                 reason="Missing Quant or Analyst data"
             ).model_dump(mode='json')
             
        signals = quant_out['signals'] # These are dicts now
        sentiment_score = analyst_out['sentiment_score']
        
        best_signal = None
        reasoning = "No actionable signals generated."
        
        # Logic: Take the first valid signal that aligns with sentiment
        target_signal_dict = None
        
        for sig_dict in signals:
            signal_type = sig_dict['signal']
            
            # Sentiment Check
            if signal_type == "BUY" and sentiment_score < -0.2:
                logger.info(f"Quant BUY rejected due to negative sentiment ({sentiment_score:.2f})")
                continue
            if signal_type == "SELL" and sentiment_score > 0.2:
                logger.info(f"Quant SELL rejected due to positive sentiment ({sentiment_score:.2f})")
                continue
            
            # Found a candidate
            target_signal_dict = sig_dict
            break
            
        if not target_signal_dict:
             return RiskOutput(
                 approved=False, 
                 adjusted_signal=None, 
                 reason="All signals rejected by sentiment or no signals found"
             ).model_dump(mode='json')
             
        # Risk Check
        entry_price = target_signal_dict.get('entry_price')
        stop_loss = target_signal_dict.get('stop_loss')
        
        if not entry_price or not stop_loss:
             return RiskOutput(
                 approved=False, 
                 adjusted_signal=None, 
                 reason="Signal missing entry or stop loss"
             ).model_dump(mode='json')

        # Volatility Adjustment (ATR)
        try:
            raw_candles = quant_out.get('price_candles', [])
            if raw_candles:
                df = pd.DataFrame(raw_candles)
                # Ensure columns match what Indicators expects (lowercase)
                # PriceCandle model has lowercase.
                if 'high' in df.columns and 'low' in df.columns and 'close' in df.columns:
                    atr_series = Indicators.atr(df['high'], df['low'], df['close'])
                    current_atr = atr_series.iloc[-1]
                    
                    if current_atr > 0:
                        # Check if SL is too tight (< 1 ATR)
                        dist = abs(entry_price - stop_loss)
                        if dist < current_atr:
                            logger.info(f"RiskAgent: Stop Loss too tight ({dist:.2f} < ATR {current_atr:.2f}). Adjusting to 1.5 ATR.")
                            if target_signal_dict['signal'] == 'BUY':
                                stop_loss = entry_price - (1.5 * current_atr)
                            else:
                                stop_loss = entry_price + (1.5 * current_atr)
                                
                        # Store adjusted SL back in dict for reporting
                        target_signal_dict['stop_loss'] = stop_loss
        except Exception as e:
            logger.warning(f"RiskAgent: Failed to calculate ATR for adjustment: {e}")

        try:
            # Use direct logic call instead of HTTP
            result_obj = check_risk_logic(
                account_size=account_size,
                risk_per_trade_percent=1.0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                symbol=symbol,
                current_exposure=current_exposure
            )
            
            if result_obj.approved:
                # Update signal with calculated size
                target_signal_dict['position_size'] = result_obj.position_size_shares
                
                return RiskOutput(
                    approved=True, 
                    adjusted_signal=TradeSignal(**target_signal_dict), 
                    reason=result_obj.reason
                ).model_dump(mode='json')
            else:
                return RiskOutput(
                    approved=False, 
                    adjusted_signal=None, 
                    reason=result_obj.reason
                ).model_dump(mode='json')
                
        except Exception as e:
            logger.error(f"RiskAgent Error: {e}")
            return RiskOutput(
                approved=False, 
                adjusted_signal=None, 
                reason=f"Error checking risk: {e}"
            ).model_dump(mode='json')
