# import httpx - removed
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.models import TradeSignal
from backend.configs.settings import settings
import logging
from backend.mcp_tools.risk_rules_tool import check_risk_logic
import pandas as pd
from backend.core.indicators import Indicators

logger = logging.getLogger(__name__)

class RiskOutput(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    approved: bool
    adjusted_signal: Optional[TradeSignal]
    reason: str
    risk_analysis: Dict[str, Any] = {}

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
        
        # Calculate Volatility & Risk Level
        volatility_score = 0.0
        risk_level = "Medium"
        
        try:
            raw_candles = quant_out.get('price_candles', [])
            if raw_candles:
                df = pd.DataFrame(raw_candles)
                if 'close' in df.columns:
                    returns = df['close'].pct_change().dropna()
                    # Annualized Volatility
                    volatility_score = returns.std() * (252 ** 0.5)
                    
                    if volatility_score < 0.20:
                        risk_level = "Low"
                    elif volatility_score < 0.40:
                        risk_level = "Medium"
                    else:
                        risk_level = "High"
        except Exception as e:
            logger.warning(f"RiskAgent: Failed to calculate volatility: {e}")

        best_signal = None
        best_score = -1.0
        reasoning = "No actionable signals generated."
        
        # Logic: Score trades based on (Technical Confidence * 0.6) + (Sentiment Alignment * 0.4)
        target_signal_dict = None
        
        for sig_dict in signals:
            signal_type = sig_dict['signal']
            confidence = sig_dict.get('agent_confidence', 0.5)
            
            # 1. Alignment Score (-1.0 to 1.0)
            # If BUY, we want positive sentiment. If SELL, negative.
            if signal_type == "BUY":
                alignment = sentiment_score
            else:
                alignment = -sentiment_score
                
            # 2. Weighted Score
            # specific strategy confidence is 0-1
            # alignment is -1 to 1. 
            # We want a threshold. e.g. composite > 0.3
            
            final_score = (confidence * 0.6) + (alignment * 0.4)
            
            logger.info(f"Risk Evaluation for {signal_type}: Conf={confidence}, Sent={sentiment_score}, Score={final_score:.2f}")
            
            if final_score > 0.25: # Dynamic Threshold
                if final_score > best_score:
                    best_score = final_score
                    target_signal_dict = sig_dict
                    reasoning = (
                        f"Approved {signal_type}: Technical confidence ({confidence:.2f}) supported by "
                        f"{'positive' if alignment > 0 else 'neutral/negative'} sentiment. Score: {final_score:.2f}."
                    )
            
        risk_analysis = {
            "volatility_score": float(f"{volatility_score:.4f}"),
            "risk_level": risk_level,
            "max_drawdown": 0.0,
            "trade_score": float(f"{best_score:.2f}") if target_signal_dict else 0.0
        }

        if not target_signal_dict:
             return RiskOutput(
                 approved=False, 
                 adjusted_signal=None, 
                 reason=f"Signals rejected. Best score {best_score:.2f} (Threshold 0.25). Sentiment: {sentiment_score:.2f}",
                 risk_analysis=risk_analysis
             ).model_dump(mode='json')
             
        # Risk Check
        entry_price = target_signal_dict.get('entry_price')
        stop_loss = target_signal_dict.get('stop_loss')
        
        if not entry_price or not stop_loss:
             return RiskOutput(
                 approved=False, 
                 adjusted_signal=None, 
                 reason="Signal missing entry or stop loss",
                 risk_analysis=risk_analysis
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
                
                # Add sizing to risk analysis
                risk_analysis["suggested_entry"] = entry_price
                risk_analysis["suggested_stop_loss"] = stop_loss
                risk_analysis["suggested_position_size"] = result_obj.position_size_shares
                
                return RiskOutput(
                    approved=True, 
                    adjusted_signal=TradeSignal(**target_signal_dict), 
                    reason=result_obj.reason,
                    risk_analysis=risk_analysis
                ).model_dump(mode='json')
            else:
                return RiskOutput(
                    approved=False, 
                    adjusted_signal=None, 
                    reason=result_obj.reason,
                    risk_analysis=risk_analysis
                ).model_dump(mode='json')
                
        except Exception as e:
            logger.error(f"RiskAgent Error: {e}")
            return RiskOutput(
                approved=False, 
                adjusted_signal=None, 
                reason=f"Error checking risk: {e}",
                risk_analysis=risk_analysis
            ).model_dump(mode='json')
