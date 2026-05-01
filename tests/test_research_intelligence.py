from app.research_intelligence.research_memory import ResearchMemory
from app.research_intelligence.market_researcher import build_research_context


def test_research_journal_creation(tmp_path):
    m = ResearchMemory(tmp_path / "journal.jsonl")
    m.append({"session": "asia"})
    assert m.latest()["session"] == "asia"


def test_market_brain_context_output():
    ctx = build_research_context()
    assert "market_bias" in ctx
