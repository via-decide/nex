import asyncio
from types import SimpleNamespace

import httpx
import pytest

from api import main as api_main
from core.evidence_collector import EvidenceCollector, _llm_extract
from core.knowledge_graph import KnowledgeGraph
from core.research_planner import ResearchPlan
from core.research_synthesizer import KnowledgeGraphData, ResearchFinding, ResearchReport, ResearchSynthesizer
from core.source_discovery import _is_open_access
from core.subchat_engine import SubchatEngine, SubchatThread
from core.utils import claims_are_similar
from core.verification_engine import Confidence, VerificationReport, VerifiedClaim
from core.zayvora_integration import ZayvoraIntegration, ZayvoraRequest, ZayvoraToolType


class _FakeClient:
    class messages:
        @staticmethod
        def create(**kwargs):
            return SimpleNamespace(content=[SimpleNamespace(text="```json\n{broken\n```")])


def test_llm_extract_handles_malformed_json():
    out = _llm_extract(_FakeClient(), "model", "text", "https://example.com")
    assert out == {
        "summary": "",
        "key_claims": [],
        "citations": [],
        "extraction_confidence": 0.0,
    }


def test_llm_extract_invalid_confidence_value(monkeypatch):
    async def _fake_fetch(_http, _url):
        return "x" * 200

    monkeypatch.setattr("core.evidence_collector._fetch_generic", _fake_fetch)
    monkeypatch.setattr("core.evidence_collector._llm_extract", lambda *_: {"summary": "s", "key_claims": [], "citations": [], "extraction_confidence": "oops"})

    collector = EvidenceCollector.__new__(EvidenceCollector)
    collector._sem = asyncio.Semaphore(1)
    collector._llm = object()
    collector._model = "m"

    src = SimpleNamespace(url="https://example.com/a", title="t", source_type="web", domain="example.com")
    item = asyncio.run(collector._process(None, src))
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


def test_run_remote_handles_timeout(monkeypatch):
    class _TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr("core.zayvora_integration.httpx.AsyncClient", lambda timeout: _TimeoutClient())

    z = ZayvoraIntegration.__new__(ZayvoraIntegration)
    z._endpoint = "https://example.com"
    z._api_key = "k"
    z._use_mock = False

    req = ZayvoraRequest(tool_type=ZayvoraToolType.CUSTOM, parameters={}, context="ctx")
    out = asyncio.run(z._run_remote(req))
    assert out.status == "error"
    assert "HTTP error" in (out.error or "")


def test_run_remote_handles_invalid_json_response(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid")

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr("core.zayvora_integration.httpx.AsyncClient", lambda timeout: _Client())

    z = ZayvoraIntegration.__new__(ZayvoraIntegration)
    z._endpoint = "https://example.com"
    z._api_key = "k"
    z._use_mock = False

    req = ZayvoraRequest(tool_type=ZayvoraToolType.CUSTOM, parameters={}, context="ctx")
    out = asyncio.run(z._run_remote(req))
    assert out.status == "error"
    assert "execution error" in (out.error or "")


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
    )
    engine = SubchatEngine.__new__(SubchatEngine)
    engine._report = report
    engine._model = "m"
    engine._llm = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs: None))
    engine._threads = {"t1": SubchatThread(thread_id="t1", finding_id="missing", finding_headline="h")}
    engine._findings = {}

    chunks = list(engine.chat_stream("t1", "hello"))
    assert chunks == ["Error: finding 'missing' not found in report."]


def test_thread_lookup_with_and_without_map():
    # reset globals
    api_main._subchats.clear()
    api_main._thread_to_engine.clear()

    class _Engine:
        def __init__(self):
            self.thread = SimpleNamespace(thread_id="thr-1")

        def create_thread(self, finding_id):
            if finding_id == "bad":
                raise ValueError("bad finding")
            return self.thread

        def export_thread(self, thread_id):
            return {"thread_id": thread_id}

        def get_thread(self, thread_id):
            return self.thread if thread_id == "thr-1" else None

    api_main._subchats["run-1"] = _Engine()

    created = asyncio.run(api_main.create_subchat(api_main.SubchatCreateRequest(run_id="run-1", finding_id="ok")))
    assert created["thread_id"] == "thr-1"

    exported = asyncio.run(api_main.export_subchat("thr-1"))
    assert exported["thread_id"] == "thr-1"

    api_main._thread_to_engine.clear()
    with pytest.raises(Exception):
        asyncio.run(api_main.export_subchat("thr-1"))
