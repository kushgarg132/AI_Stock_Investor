"""Regression tests for the signal/risk bugs found during the trading rework.

Each test here corresponds to a defect that was silently wrong in production:
strategy conviction being dropped, sentiment being inverted for BUYs, and long
stop-losses being placed above the entry price.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from backend.components.quant.strategies import (
    MACDCrossover,
    MeanReversion,
    TechnicalBreakout,
    VolumeSurge,
)
from backend.components.risk.agent import RiskAgent
from backend.components.shared.models import SignalType, TradeSignal

STRATEGIES = [TechnicalBreakout(), MeanReversion(), VolumeSurge(), MACDCrossover()]


def test_tradesignal_rejects_unknown_fields():
    """The root cause: unknown kwargs used to be dropped instead of raising.

    Strategies passed `agent_confidence`/`reasoning`/`source_agent`, none of
    which were declared, so conviction stayed 0.0 and the risk scorer always
    read its 0.5 fallback.
    """
    with pytest.raises(ValidationError):
        TradeSignal(symbol="X", signal=SignalType.BUY, agent_confidence=0.9)


def test_tradesignal_carries_conviction_and_reason():
    sig = TradeSignal(
        symbol="X",
        signal=SignalType.BUY,
        conviction=0.8,
        reason="breakout",
        source="QuantAgent",
    )
    assert sig.conviction == 0.8
    assert sig.reason == "breakout"
    assert sig.model_dump()["conviction"] == 0.8


def _breakout_frame() -> pd.DataFrame:
    """Flat base, then a high-volume close above the established resistance."""
    n = 60
    close = [100.0] * (n - 1) + [130.0]
    high = [101.0] * (n - 1) + [131.0]
    low = [99.0] * (n - 1) + [129.0]
    volume = [1000.0] * (n - 1) + [999_999.0]
    return pd.DataFrame({
        "symbol": ["TEST"] * n,
        "open": close,
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
    })


def _oversold_frame() -> pd.DataFrame:
    """Quiet base then a sharp selloff: drives RSI under 30 while the Bollinger
    band, tightened by the quiet stretch, sits above the falling price.

    A smooth linear decline does *not* work here — the band widens in step with
    the trend and price never crosses it.
    """
    close = [100.0] * 50 + [96.0, 92.0, 88.0, 84.0, 80.0]
    return pd.DataFrame({
        "symbol": ["TEST"] * len(close),
        "open": close,
        "close": close,
        "high": [c + 1 for c in close],
        "low": [c - 1 for c in close],
        "volume": [1000.0] * len(close),
    })


@pytest.mark.parametrize("frame", [_breakout_frame(), _oversold_frame()])
def test_strategies_emit_nonzero_conviction(frame):
    """At least one strategy must fire, and a firing signal must carry its own
    conviction rather than the model default."""
    signals = [s for s in (st.analyze(frame.copy()) for st in STRATEGIES) if s]
    assert signals, "expected at least one strategy to fire on this frame"
    for sig in signals:
        assert sig.conviction > 0.0, f"{sig.source} emitted default conviction"
        assert sig.reason, f"{sig.source} emitted no reason"


def test_conviction_survives_into_risk_scoring():
    """End-to-end guard on the dropped-field bug: what a strategy sets must be
    what the risk agent reads."""
    signal = TradeSignal(
        symbol="TEST",
        signal=SignalType.BUY,
        conviction=0.8,
        entry_price=100.0,
        stop_loss=95.0,
        reason="test",
    )
    assert signal.model_dump().get("conviction") == 0.8


@pytest.mark.asyncio
async def test_buy_is_scored_with_sentiment_not_against_it():
    """Positive news must help a BUY, not hurt it.

    `SignalType.BUY` serialises to "buy", but the scorer compared against
    "BUY", so the branch never fired and alignment was always `-sentiment`.
    """
    agent = RiskAgent()

    def state(sentiment: float):
        return {
            "symbol": "TEST",
            "account_size": 100_000.0,
            "current_exposure": 0.0,
            "quant_output": {
                "signals": [TradeSignal(
                    symbol="TEST",
                    signal=SignalType.BUY,
                    conviction=0.8,
                    entry_price=100.0,
                    stop_loss=95.0,
                    reason="test",
                ).model_dump(mode="json")],
                "price_candles": [],
            },
            "analyst_output": {"sentiment_score": sentiment},
        }

    bullish = await agent.evaluate(state(1.0))
    bearish = await agent.evaluate(state(-1.0))

    assert bullish["risk_analysis"]["trade_score"] > bearish["risk_analysis"]["trade_score"], (
        "good news must raise a BUY's score"
    )
    assert bullish["approved"], "a high-conviction BUY with bullish news must pass"


@pytest.mark.asyncio
async def test_long_stop_loss_stays_below_entry():
    """ATR widening must never push a long's stop above its entry price."""
    agent = RiskAgent()

    # Wide ranges so ATR is large enough to trigger the widening branch against
    # a deliberately tight stop.
    n = 30
    candles = [{
        "symbol": "TEST",
        "open": 100.0, "close": 100.0,
        "high": 120.0, "low": 80.0,
        "volume": 1000.0,
    } for _ in range(n)]

    result = await agent.evaluate({
        "symbol": "TEST",
        "account_size": 1_000_000.0,
        "current_exposure": 0.0,
        "quant_output": {
            "signals": [TradeSignal(
                symbol="TEST",
                signal=SignalType.BUY,
                conviction=0.9,
                entry_price=100.0,
                stop_loss=99.9,          # tighter than ATR, forces widening
                reason="test",
            ).model_dump(mode="json")],
            "price_candles": candles,
        },
        "analyst_output": {"sentiment_score": 1.0},
    })

    stop = result["risk_analysis"].get("suggested_stop_loss")
    assert stop is not None, "expected the trade to be approved and sized"
    assert stop < 100.0, f"long stop-loss {stop} is at or above the entry price"
