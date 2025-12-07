import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.agents.analyst_agent import AnalystAgent
from backend.agents.quant_agent import QuantAgent
from backend.agents.master_agent import MasterAgent
from backend.models import SignalType, TradeSignal, NewsArticle, FinancialEvent, PriceCandle, Trend

# ----------------- Analyst Agent Test ----------------- #
@pytest.mark.asyncio
async def test_analyst_agent_run(mock_db):
    agent = AnalystAgent()
    
    # Create valid mock objects
    mock_article = NewsArticle(
        title="Test News", url="http://test.com", source="Test", published_at="2023-01-01T00:00:00",
        sentiment="positive", sentiment_score=0.8, impact_score=5
    )
    
    # Patch dependencies
    # Note: AnalystAgent imports them directly, so we patch where they are used or imported
    with patch("backend.agents.analyst_agent.fetch_news_logic", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [mock_article]
        
        with patch("backend.agents.analyst_agent.analyze_sentiment_logic", new_callable=AsyncMock) as mock_sentiment:
            mock_sentiment.return_value = [mock_article]
            
            with patch("backend.agents.analyst_agent.classify_events_logic", new_callable=AsyncMock) as mock_events:
                 mock_events.return_value = []
                 
                 with patch("backend.agents.analyst_agent.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = "Market is bullish."
                    
                    result = await agent.analyze({"symbol": "AAPL"})
                    
                    assert result["sentiment_score"] == 0.8
                    assert result["summary"] == "Market is bullish."

# ----------------- Quant Agent Test ----------------- #
@pytest.mark.asyncio
async def test_quant_agent_run(mock_db):
    agent = QuantAgent()
    
    # Mock candles
    candles = [
        PriceCandle(symbol="AAPL", timestamp="2023-01-01T00:00:00", open=100, high=110, low=90, close=105, volume=1000)
        for _ in range(50)
    ]
    
    with patch("backend.agents.quant_agent.fetch_price_history_logic", new_callable=AsyncMock) as mock_fetch:
        # fetch_price_history_logic returns (candles, source)
        mock_fetch.return_value = (candles, "yahoo")
        
        with patch("backend.agents.quant_agent.detect_trend_logic", return_value=(Trend.UP, "Up")):
            with patch("backend.agents.quant_agent.detect_support_resistance_logic") as mock_sr:
                # Mock result object for S/R
                mock_sr_resp = MagicMock()
                mock_sr_resp.nearest_support = 90.0
                mock_sr_resp.nearest_resistance = 110.0
                mock_sr.return_value = mock_sr_resp
                
                result = await agent.analyze({"symbol": "AAPL"})
                
                assert result["symbol"] == "AAPL"
                assert result["trend"] == "up"
                assert len(result["price_candles"]) == 50

# ----------------- Master Agent Test ----------------- #
@pytest.mark.asyncio
async def test_master_agent_run(mock_db):
    agent = MasterAgent()
    
    # Mock sub-agents
    agent.analyst = AsyncMock()
    agent.analyst.analyze.return_value = {
        "summary": "Good", 
        "sentiment_score": 0.8, 
        "impact_score": 5,
        "sentiment_analysis": {},
        "news_articles": [],
        "events": []
    }
    
    agent.quant = AsyncMock()
    agent.quant.analyze.return_value = {
        "signals": [{"signal": "buy", "confidence": 0.9}],
        "trend": "up",
        "nearest_support": 100,
        "nearest_resistance": 110,
        "price_candles": [],
        "indicators": {},
        "market_data": {}
    }
    
    agent.risk = AsyncMock()
    agent.risk.evaluate.return_value = {
        "approved": True,
        "position_size": 10,
        "reason": "Safe",
        "adjusted_signal": {"symbol": "AAPL", "signal": "buy", "entry_price": 100},
        "risk_analysis": {}
    }
    
    # Mock search and memory
    with patch("backend.agents.master_agent.resolve_company_query", new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = {"symbol": "AAPL", "peers": []}
        
        with patch("backend.agents.master_agent.memory_manager.get_memories", new_callable=AsyncMock) as mock_mem:
            mock_mem.return_value = []
            
            with patch("backend.agents.master_agent.memory_manager.add_memory", new_callable=AsyncMock):
                
                 with patch("backend.agents.master_agent.llm_service.get_completion", new_callable=AsyncMock) as mock_llm:
                    mock_llm.return_value = "Buy it."
                    
                    # Run master
                    output = await agent.run("AAPL", account_size=1000)
                    
                    assert output.decision == SignalType.BUY
                    assert output.reasoning == "Safe | LLM: Buy it."
