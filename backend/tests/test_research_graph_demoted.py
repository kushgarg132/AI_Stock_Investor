"""backend.research.graph is a research-report-generator only -- it must not
carry any decision-making or risk-scoring symbol forward from the old
MasterAgent pipeline (backend/components/master/agent.py). Scoring and
decisions live in backend.scoring / backend.strategies now."""

import backend.research.graph as graph_module
from backend.research.graph import ResearchAgent, ResearchReport


def test_module_exports_no_decision_or_risk_symbols():
    for name in ("decision_node", "decision_maker", "risk_node", "risk_assessment", "RiskAgent", "QuantAgent"):
        assert not hasattr(graph_module, name), f"unexpected leftover symbol: {name}"


def test_research_agent_has_no_decision_or_risk_methods():
    for name in ("decision_node", "risk_node"):
        assert not hasattr(ResearchAgent, name), f"unexpected leftover method: {name}"


def test_research_report_has_no_decision_fields():
    fields = ResearchReport.model_fields
    for name in ("decision", "final_signal", "agent_confidence"):
        assert name not in fields, f"unexpected leftover field: {name}"


def test_research_report_has_expected_fields():
    fields = set(ResearchReport.model_fields)
    expected = {
        "symbol", "company_info", "sentiment_score", "impact_score",
        "sentiment", "news_articles", "events", "analyst_summary",
        "thesis", "peers",
    }
    assert expected <= fields
