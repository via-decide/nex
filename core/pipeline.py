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
from .zayvora_integration import ZayvoraIntegration


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
    enable_zayvora: bool = False
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
        self._zayvora = ZayvoraIntegration() if self.config.enable_zayvora else None

    async def run(self, question: str) -> PipelineResult:
        """Run the full pipeline and return a PipelineResult."""
        events: list[PipelineEvent] = []
        try:
            # Stage 1 — Research Planning
            events.append(PipelineEvent("planning", "started", "Generating research plan..."))
            plan = await self._planner.plan(question, depth_hint=self.config.depth)
            events.append(PipelineEvent(
                "planning", "completed",
                f"Plan generated: {len(plan.subtopics)} subtopics, {len(plan.keywords)} keywords.",
                {"topic": plan.topic, "depth": plan.depth},
            ))

            # Stage 2 — Source Discovery
            events.append(PipelineEvent("discovery", "started", "Discovering sources..."))
            sources = await self._discovery.discover_sources(
                plan.search_queries,
                source_types=self.config.source_types,
            )
            sources = self._discovery.rank_sources(sources, keywords=plan.keywords)
            events.append(PipelineEvent(
                "discovery", "completed",
                f"Found {len(sources)} open-access sources.",
                {"source_count": len(sources)},
            ))

            # Stage 3 — Evidence Collection
            events.append(PipelineEvent("collection", "started", "Collecting evidence..."))
            evidence = await self._collector.collect(
                sources, max_sources=self.config.max_sources
            )
            events.append(PipelineEvent(
                "collection", "completed",
                f"Extracted evidence from {len(evidence)} sources.",
                {
                    "evidence_count": len(evidence),
                    "total_claims": sum(e.claim_count for e in evidence),
                },
            ))

            # Stage 4 — Verification
            events.append(PipelineEvent("verification", "started", "Verifying claims..."))
            verification = self._verifier.verify(evidence)
            events.append(PipelineEvent(
                "verification", "completed",
                (
                    f"Verification complete: "
                    f"{len(verification.verified)} VERIFIED, "
                    f"{len(verification.likely)} LIKELY, "
                    f"{len(verification.low_confidence)} LOW_CONFIDENCE."
                ),
                {
                    "verified": len(verification.verified),
                    "likely": len(verification.likely),
                    "low_confidence": len(verification.low_confidence),
                    "contradictions": len(verification.contradictions),
                },
            ))

            # Stage 5 — Knowledge Graph
            events.append(PipelineEvent("knowledge_graph", "started", "Building knowledge graph..."))
            graph = self._kg_builder.build(verification, topic=plan.topic)
            events.append(PipelineEvent(
                "knowledge_graph", "completed",
                f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges.",
                {"nodes": len(graph.nodes), "edges": len(graph.edges)},
            ))

            # Stage 6 — Synthesis
            events.append(PipelineEvent("synthesis", "started", "Synthesizing research report..."))
            report = self._synthesizer.synthesize(
                plan, verification, graph, total_sources=len(sources)
            )
            events.append(PipelineEvent(
                "synthesis", "completed",
                f"Report generated: {len(report.key_findings)} key findings.",
                {"findings": len(report.key_findings)},
            ))

            return PipelineResult(
                plan=plan,
                sources=sources,
                evidence=evidence,
                verification=verification,
                knowledge_graph=graph,
                report=report,
                events=events,
                success=True,
            )

        except Exception as exc:
            events.append(PipelineEvent("error", "error", str(exc)))
            raise

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
