"""
Deep Research Pipeline Orchestrator

Ties all modules together into a single, end-to-end async pipeline:

  User Question
  → ResearchPlanner        (decompose question)
  → SourceDiscovery        (find open-access sources)
  → EvidenceCollector      (fetch & extract evidence)
  → VerificationEngine     (cross-check & score claims)
  → KnowledgeGraph         (build concept graph)
  → ResearchSynthesizer    (generate report)
  → [ZayvoraIntegration]   (optional: run simulations)
  → ResearchReport         (structured output)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

from .research_planner import ResearchPlanner, ResearchPlan
from .source_discovery import SourceDiscovery, DiscoveredSource
from .evidence_collector import EvidenceCollector, EvidenceItem
from .verification_engine import VerificationEngine, VerificationReport
from .knowledge_graph import KnowledgeGraph, KnowledgeGraphData
from .research_synthesizer import ResearchSynthesizer, ResearchReport
from .hallucination_guard import HallucinationGuard, HallucinationGuardResult
from .zayvora_integration import ZayvoraIntegration, ZayvoraRequest, ZayvoraToolType


# ---------------------------------------------------------------------------
# Progress event (for streaming pipeline status to the UI)
# ---------------------------------------------------------------------------

@dataclass
class PipelineEvent:
    stage: str
    status: str           # "started" | "completed" | "error"
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    depth: str = "standard"          # "standard" | "deep" | "exhaustive"
    max_sources: int = 30
    enable_zayvora: bool = True
    max_revision_cycles: int = 2
    verification_threshold: float = 0.65
    source_types: list[str] = field(
        default_factory=lambda: ["wikipedia", "arxiv", "semanticscholar"]
    )
    use_llm_contradiction: bool = False


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    plan: ResearchPlan
    sources: list[DiscoveredSource]
    evidence: list[EvidenceItem]
    verification: VerificationReport
    knowledge_graph: KnowledgeGraphData
    report: ResearchReport
    hallucination_guard: HallucinationGuardResult | None
    events: list[PipelineEvent]
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class DeepResearchPipeline:
    """
    Orchestrates the full deep research pipeline.

    Usage (async):
        pipeline = DeepResearchPipeline()
        result = await pipeline.run("How do V2X systems reduce traffic accidents?")

    Usage (streaming):
        async for event in pipeline.run_streaming("..."):
            print(event.stage, event.message)
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self._planner = ResearchPlanner()
        self._discovery = SourceDiscovery(max_sources=self.config.max_sources)
        self._collector = EvidenceCollector()
        self._verifier = VerificationEngine(
            use_llm_contradiction=self.config.use_llm_contradiction
        )
        self._kg_builder = KnowledgeGraph()
        self._synthesizer = ResearchSynthesizer()
        self._hallucination_guard = HallucinationGuard()
        self._zayvora = ZayvoraIntegration()

    async def run(self, question: str) -> PipelineResult:
        """Run Zayvora's 6-stage filtered research loop until verified truth passes."""
        events: list[PipelineEvent] = []
        last_error: str | None = None

        for cycle in range(1, self.config.max_revision_cycles + 2):
            try:
                events.append(PipelineEvent("decompose", "started", "STAGE 1/6 DECOMPOSE: planning sub-questions and evidence rules...", {"cycle": cycle}))
                plan = await self._planner.plan(question, depth_hint=self.config.depth)
                evidence_rules = self._evidence_rules(plan)
                events.append(PipelineEvent(
                    "decompose", "completed",
                    f"Decomposed into {len(plan.subtopics)} sub-questions with strict evidence criteria.",
                    {"topic": plan.topic, "criteria": evidence_rules, "cycle": cycle},
                ))

                events.append(PipelineEvent("retrieve", "started", "STAGE 2/6 RETRIEVE: discovering high-signal sources and pre-filtering spam...", {"cycle": cycle}))
                sources = await self._discovery.discover_sources(
                    plan.search_queries,
                    source_types=self.config.source_types,
                    event_callback=lambda stage, message, data: events.append(
                        PipelineEvent(stage, "started", message, data)
                    ),
                )
                sources = self._prefilter_sources(
                    self._discovery.rank_sources(sources, keywords=plan.keywords)
                )
                evidence = await self._collector.collect(sources, max_sources=self.config.max_sources)
                events.append(PipelineEvent(
                    "retrieve", "completed",
                    f"Collected {len(evidence)} evidence records from {len(sources)} filtered sources.",
                    {"source_count": len(sources), "evidence_count": len(evidence), "cycle": cycle},
                ))

                events.append(PipelineEvent("synthesize", "started", "STAGE 3/6 SYNTHESIZE: mapping claims into a directed knowledge graph...", {"cycle": cycle}))
                verification = self._verifier.verify(evidence)
                filtered_verification = self._verifier.excise_low_confidence(verification)
                graph = self._kg_builder.build(filtered_verification, topic=plan.topic)
                anomalies = self._isolated_nodes(graph)
                events.append(PipelineEvent(
                    "synthesize", "completed",
                    f"Graph built with {len(graph.nodes)} nodes; {len(anomalies)} isolated anomalies flagged.",
                    {"nodes": len(graph.nodes), "edges": len(graph.edges), "anomalies": anomalies, "cycle": cycle},
                ))

                events.append(PipelineEvent("calculate", "started", "STAGE 4/6 CALCULATE: deterministically checking quantitative claims with Zayvora...", {"cycle": cycle}))
                calculations = await self._calculate_claims(filtered_verification)
                events.append(PipelineEvent(
                    "calculate", "completed",
                    f"Zayvora evaluated {len(calculations)} mathematical/statistical/logic claims.",
                    {"calculation_count": len(calculations), "cycle": cycle},
                ))

                events.append(PipelineEvent("verify", "started", "STAGE 5/6 VERIFY: cross-examining graph, metrics, and invariants...", {"cycle": cycle}))
                revise, reasons, score = self._verifier.should_revise(
                    verification, graph, calculations, min_confidence=self.config.verification_threshold
                )
                events.append(PipelineEvent(
                    "verify", "completed",
                    f"Confidence score {score:.2f}; {len(verification.low_confidence)} LOW_CONFIDENCE claims excised.",
                    {
                        "verified": len(verification.verified),
                        "likely": len(verification.likely),
                        "low_confidence_excised": len(verification.low_confidence),
                        "score": score,
                        "revise": revise,
                        "reasons": reasons,
                        "cycle": cycle,
                    },
                ))

                events.append(PipelineEvent("revise", "started", "STAGE 6/6 REVISE: deciding whether another DECOMPOSE pass is required...", {"cycle": cycle}))
                if revise:
                    if cycle <= self.config.max_revision_cycles:
                        events.append(PipelineEvent(
                            "revise", "completed",
                            "Verification threshold failed; autonomously restarting at DECOMPOSE for better data.",
                            {"reasons": reasons, "next_cycle": cycle + 1},
                        ))
                        continue
                    raise RuntimeError(f"Verification threshold failed after revision loop: {reasons}")

                report = self._synthesizer.synthesize(
                    plan, filtered_verification, graph, total_sources=len(sources), evidence_items=evidence
                )
                guard_result = await self._hallucination_guard.run(report, evidence)
                events.append(PipelineEvent(
                    "revise", "completed",
                    "Verified truth threshold passed; final research report released.",
                    {"findings": len(report.key_findings), "hallucination_score": guard_result.hallucination_score, "cycle": cycle},
                ))

                return PipelineResult(
                    plan=plan, sources=sources, evidence=evidence, verification=filtered_verification,
                    knowledge_graph=graph, report=report, hallucination_guard=guard_result,
                    events=events, success=True,
                )
            except Exception as exc:
                last_error = str(exc)
                events.append(PipelineEvent("error", "error", last_error, {"cycle": cycle}))
                raise

        raise RuntimeError(last_error or "Research pipeline failed verification threshold.")

    def _evidence_rules(self, plan: ResearchPlan) -> dict[str, Any]:
        return {
            "valid_sources": ["arxiv", "semanticscholar", ".gov", ".edu", "open datasets"],
            "drop": ["SEO spam", "opinion blogs", "low-authority URLs", "paywalled/login-gated pages"],
            "query_specific_types": plan.source_types,
            "sub_questions": plan.subtopics,
        }

    def _prefilter_sources(self, sources: list[DiscoveredSource]) -> list[DiscoveredSource]:
        allowed = ("arxiv.org", "semanticscholar.org", "wikipedia.org", ".gov", ".edu", "nih.gov", "nasa.gov")
        spam = ("medium.com", "substack.com", "quora.com", "reddit.com", "pinterest.", "forbes.com")
        filtered = []
        for src in sources:
            domain = src.domain.lower().lstrip("www.")
            if any(bad in domain for bad in spam):
                continue
            if src.source_type in {"engineering_blog", "web"} and not any(ok in domain for ok in allowed):
                continue
            filtered.append(src)
        return filtered[: self.config.max_sources]

    def _isolated_nodes(self, graph: KnowledgeGraphData) -> list[str]:
        linked = {e.source_id for e in graph.edges} | {e.target_id for e in graph.edges}
        return [n.id for n in graph.nodes if n.node_type != "entity" and n.id not in linked]

    async def _calculate_claims(self, verification: VerificationReport) -> list[dict[str, Any]]:
        quantitative = [c for c in verification.high_confidence_claims if any(ch.isdigit() for ch in c.claim)][:5]
        if not self._zayvora or not quantitative:
            return []
        requests = [
            ZayvoraRequest(
                tool_type=ZayvoraToolType.NUMERICAL_MODELING,
                parameters={"claim": claim.claim, "constraints": "known physical/system invariants"},
                context=claim.claim,
            )
            for claim in quantitative
        ]
        return [
            {
                "status": r.status,
                "summary": r.summary,
                "tool_type": r.request.tool_type.value,
                "context": r.request.context,
                "error": r.error,
            }
            for r in await self._zayvora.run_batch(requests)
        ]

    async def run_streaming(self, question: str) -> AsyncIterator[PipelineEvent]:
        """
        Run the pipeline and yield PipelineEvents as each stage completes.
        """
        # This is a simplified streaming wrapper — yields events progressively
        events_queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

        async def _run() -> None:
            try:
                result = await self.run(question)
                for event in result.events:
                    await events_queue.put(event)
            except Exception as exc:
                await events_queue.put(PipelineEvent("error", "error", str(exc)))
            finally:
                await events_queue.put(None)  # sentinel

        task = asyncio.create_task(_run())
        while True:
            event = await events_queue.get()
            if event is None:
                break
            yield event
        await task
