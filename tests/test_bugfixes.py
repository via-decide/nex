import asyncio
from types import SimpleNamespace

import httpx
import pytest

from api import main as api_main
from core.evidence_collector import EvidenceCollector, _llm_extract
from core.hallucination_guard import HallucinationGuard
from core.knowledge_graph import KnowledgeGraph
from core.research_planner import ResearchPlan
from core.research_synthesizer import KnowledgeGraphData, ResearchReport, ResearchSynthesizer
from core.source_discovery import _is_open_access
from core.subchat_engine import SubchatEngine, SubchatThread
from core.utils import claims_are_similar
from core.verification_engine import Confidence, VerificationReport, VerifiedClaim
from core.zayvora_integration import ZayvoraIntegration, ZayvoraRequest, ZayvoraToolType


class _FakeClient:
    async def generate_json(self, *args, **kwargs):
        import json
        raise json.JSONDecodeError("broken", "doc", 0)


def test_llm_extract_handles_malformed_json():
    out = asyncio.run(_llm_extract(_FakeClient(), "text", "https://example.com"))
    assert out == {
        "summary": "",
        "key_claims": [],
        "citations": [],
        "published_at": None,
        "extraction_confidence": 0.0,
    }


def test_llm_extract_invalid_confidence_value(monkeypatch):
    async def _fake_fetch(_http, _url):
        return "x" * 200

    monkeypatch.setattr("core.evidence_collector._fetch_generic", _fake_fetch)
    async def _mock_extract(*args, **kwargs):
        return {"summary": "s", "key_claims": [], "citations": [], "extraction_confidence": "oops"}
    monkeypatch.setattr("core.evidence_collector._llm_extract", _mock_extract)

    async def run_test():
        collector = EvidenceCollector.__new__(EvidenceCollector)
        collector._sem = asyncio.Semaphore(1)
        collector._llm = object()
        collector._model = "m"
        src = SimpleNamespace(url="https://example.com/a", title="t", source_type="web", domain="example.com", uid="e1")
        return await collector._process(None, src)

    item = asyncio.run(run_test())
    assert item is not None
    assert item.extraction_confidence == 0.5


def test_call_llm_handles_invalid_json():
    synth = ResearchSynthesizer.__new__(ResearchSynthesizer)
    synth._model = "m"
    synth._llm = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(content=[SimpleNamespace(text="{not-json")])) )

    plan = ResearchPlan(topic="Topic", subtopics=["a"], keywords=[], search_queries=[], source_types=[], depth="standard", estimated_sources=0, strategy_notes="", raw={})
    out = synth._call_llm(plan, "digest")
    assert out["title"] == "Research Report: Topic"
    assert out["key_findings"] == []


def test_extract_graph_handles_invalid_json():
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg._model = "m"
    kg._llm = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(content=[SimpleNamespace(text="{bad")])) )
    out = kg._extract_graph(["claim"], "Topic")
    assert out == {"concepts": [], "relationships": []}





def test_claims_are_similar_edge_cases():
    assert claims_are_similar("", "") is False
    assert claims_are_similar("The battery improves efficiency", "Battery improves efficiency") is True


def test_is_open_access_unknown_domain_false():
    assert _is_open_access("https://unknown-paywallish-domain.example/path") is False


def test_chat_stream_invalid_finding_id():
    report = ResearchReport(
        title="t",
        executive_summary="s",
        key_findings=[],
        evidence_sections=[],
        limitations="l",
        future_research=[],
        sources=[],
        knowledge_graph=KnowledgeGraphData(nodes=[], edges=[], root_topic="r"),
        generated_at="now",
        topic="topic",
        depth="standard",
        total_sources_analyzed=0,
        source_freshness_summary=None,
        executive_brief=None,
    )
    engine = SubchatEngine.__new__(SubchatEngine)
    engine._report = report
    engine._model = "m"
    engine._llm = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs: None))
    engine._threads = {"t1": SubchatThread(thread_id="t1", finding_id="missing", finding_headline="h")}
    engine._findings = {}

    chunks = list(engine.chat_stream("t1", "hello"))
    assert chunks == ["Error: finding 'missing' not found in report."]





def test_hallucination_guard_score(monkeypatch):
    guard = HallucinationGuard.__new__(HallucinationGuard)
    guard._model = "m"
    guard._llm = None

    async def _fake_check_sentences(sentences, _digest):
        out = []
        for s in sentences:
            out.append(SimpleNamespace(sentence=s, grounded=("ungrounded" not in s), suggested_correction=s))
        return out

    guard._check_sentences = _fake_check_sentences

    report = ResearchReport(
        title="t",
        executive_summary="Grounded sentence. ungrounded sentence.",
        key_findings=[SimpleNamespace(id="f1", detail="Another grounded sentence.")],
        evidence_sections=[],
        limitations="l",
        future_research=[],
        sources=[],
        knowledge_graph=KnowledgeGraphData(nodes=[], edges=[], root_topic="r"),
        generated_at="now",
        topic="topic",
        depth="standard",
        total_sources_analyzed=0,
        source_freshness_summary=None,
        executive_brief=None,
    )
    evidence = [SimpleNamespace(evidence_item_id="e1", summary="sum", key_claims=["claim"])]
    result = asyncio.run(guard.run(report, evidence))
    assert result.hallucination_score > 0
