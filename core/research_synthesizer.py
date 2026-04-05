"""
Module 6 — Research Synthesizer

Combines verified evidence and the knowledge graph into a structured,
narrative research report. Produces multiple export formats.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic

from .verification_engine import VerificationReport, Confidence
from .knowledge_graph import KnowledgeGraphData
from .research_planner import ResearchPlan


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResearchFinding:
    id: str
    headline: str                  # one-sentence finding
    detail: str                    # 2-4 sentence elaboration
    confidence: str                # VERIFIED | LIKELY | LOW_CONFIDENCE
    supporting_sources: list[str]
    related_concepts: list[str]
    subchat_seed: str              # suggested question to seed subchat thread


@dataclass
class ResearchReport:
    title: str
    executive_summary: str
    key_findings: list[ResearchFinding]
    evidence_sections: list[dict[str, Any]]
    limitations: str
    future_research: list[str]
    sources: list[dict[str, str]]
    knowledge_graph: KnowledgeGraphData
    generated_at: str
    topic: str
    depth: str
    total_sources_analyzed: int

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "topic": self.topic,
            "depth": self.depth,
            "generated_at": self.generated_at,
            "total_sources_analyzed": self.total_sources_analyzed,
            "executive_summary": self.executive_summary,
            "key_findings": [
                {
                    "id": f.id,
                    "headline": f.headline,
                    "detail": f.detail,
                    "confidence": f.confidence,
                    "supporting_sources": f.supporting_sources,
                    "related_concepts": f.related_concepts,
                    "subchat_seed": f.subchat_seed,
                }
                for f in self.key_findings
            ],
            "evidence_sections": self.evidence_sections,
            "limitations": self.limitations,
            "future_research": self.future_research,
            "sources": self.sources,
            "knowledge_graph": self.knowledge_graph.to_dict(),
        }

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# {self.title}\n")
        lines.append(f"**Generated:** {self.generated_at}  ")
        lines.append(f"**Depth:** {self.depth}  ")
        lines.append(f"**Sources analyzed:** {self.total_sources_analyzed}\n")
        lines.append("---\n")
        lines.append("## Executive Summary\n")
        lines.append(self.executive_summary + "\n")
        lines.append("## Key Findings\n")
        for i, f in enumerate(self.key_findings, 1):
            badge = {"VERIFIED": "✓", "LIKELY": "~", "LOW_CONFIDENCE": "?"}[f.confidence]
            lines.append(f"### {i}. {f.headline}  `[{badge} {f.confidence}]`\n")
            lines.append(f.detail + "\n")
            if f.supporting_sources:
                src_list = "  ".join(f"[{j+1}]({u})" for j, u in enumerate(f.supporting_sources[:3]))
                lines.append(f"*Sources:* {src_list}\n")
        lines.append("## Evidence Sections\n")
        for section in self.evidence_sections:
            lines.append(f"### {section.get('title', 'Section')}\n")
            lines.append(section.get("content", "") + "\n")
        lines.append("## Limitations\n")
        lines.append(self.limitations + "\n")
        lines.append("## Future Research\n")
        for item in self.future_research:
            lines.append(f"- {item}")
        lines.append("\n## Sources\n")
        for i, src in enumerate(self.sources, 1):
            lines.append(f"{i}. [{src.get('title', src['url'])}]({src['url']}) — *{src.get('type', 'web')}*")
        lines.append("\n## Knowledge Graph\n")
        lines.append("```mermaid")
        lines.append(self.knowledge_graph.to_mermaid())
        lines.append("```")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# LLM synthesis prompts
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """You are a senior research analyst producing an authoritative research report.
Given verified claims, a research plan, and topic, produce a structured synthesis in JSON.
Return ONLY valid JSON.

Schema:
{
  "title": "<descriptive research title>",
  "executive_summary": "<4-6 sentence authoritative summary>",
  "key_findings": [
    {
      "id": "finding-1",
      "headline": "<one-sentence finding>",
      "detail": "<2-4 sentence elaboration>",
      "subchat_seed": "<follow-up question a researcher might ask>",
      "related_concepts": ["<concept1>", ...]
    }
  ],  // 6-12 findings
  "evidence_sections": [
    {
      "title": "<section title>",
      "content": "<3-5 paragraph analysis of this evidence cluster>"
    }
  ],  // 3-6 sections matching subtopics
  "limitations": "<paragraph on research limitations and gaps>",
  "future_research": ["<specific research direction 1>", ...]  // 4-8 items
}

Rules:
- Be precise and technical.
- Base every claim on the provided evidence.
- key_findings must be ordered from most impactful to least.
- Acknowledge uncertainty where present.
"""


class ResearchSynthesizer:
    """
    Synthesize a full research report from verified evidence.

    Usage:
        synthesizer = ResearchSynthesizer()
        report = synthesizer.synthesize(plan, report, graph, evidence_items)
    """

    def __init__(self, model: str = "claude-opus-4-6") -> None:
        self._llm = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model

    def synthesize(
        self,
        plan: ResearchPlan,
        verification_report: VerificationReport,
        graph: KnowledgeGraphData,
        total_sources: int,
    ) -> ResearchReport:
        """Produce a complete ResearchReport."""
        # Build claim digest
        claim_digest = self._build_claim_digest(verification_report)
        raw = self._call_llm(plan, claim_digest)

        # Build source list from verification report
        all_sources: dict[str, str] = {}  # url -> type
        for vc in verification_report.all_claims:
            for src in vc.supporting_sources:
                src_type = "web"
                if "arxiv" in src:
                    src_type = "arxiv"
                elif "wikipedia" in src:
                    src_type = "wikipedia"
                elif any(t in src for t in [".gov", ".edu"]):
                    src_type = "gov"
                all_sources[src] = src_type

        sources = [
            {"url": url, "title": url.split("/")[-1], "type": src_type}
            for url, src_type in list(all_sources.items())[:50]
        ]

        # Attach confidence to findings
        findings = []
        verified_claims = {vc.claim for vc in verification_report.verified}
        likely_claims = {vc.claim for vc in verification_report.likely}
        claim_sources: dict[str, list[str]] = {
            vc.claim: vc.supporting_sources for vc in verification_report.all_claims
        }

        for i, f in enumerate(raw.get("key_findings", []), 1):
            headline = f.get("headline", "")
            # Match confidence from verification
            conf = Confidence.LOW_CONFIDENCE.value
            matched_sources: list[str] = []
            for vc_claim in verification_report.all_claims:
                if _claims_are_similar(headline, vc_claim.claim):
                    conf = vc_claim.confidence.value
                    matched_sources = vc_claim.supporting_sources[:3]
                    break

            findings.append(ResearchFinding(
                id=f"finding-{i}",
                headline=headline,
                detail=f.get("detail", ""),
                confidence=conf,
                supporting_sources=matched_sources,
                related_concepts=f.get("related_concepts", []),
                subchat_seed=f.get("subchat_seed", f"Tell me more about: {headline}"),
            ))

        return ResearchReport(
            title=raw.get("title", f"Research Report: {plan.topic}"),
            executive_summary=raw.get("executive_summary", ""),
            key_findings=findings,
            evidence_sections=raw.get("evidence_sections", []),
            limitations=raw.get("limitations", ""),
            future_research=raw.get("future_research", []),
            sources=sources,
            knowledge_graph=graph,
            generated_at=datetime.utcnow().isoformat() + "Z",
            topic=plan.topic,
            depth=plan.depth,
            total_sources_analyzed=total_sources,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_claim_digest(self, report: VerificationReport) -> str:
        lines: list[str] = []
        lines.append("=== VERIFIED CLAIMS ===")
        for vc in report.verified[:20]:
            lines.append(f"[VERIFIED] {vc.claim}")
        lines.append("\n=== LIKELY CLAIMS ===")
        for vc in report.likely[:20]:
            lines.append(f"[LIKELY] {vc.claim}")
        lines.append("\n=== LOW CONFIDENCE CLAIMS ===")
        for vc in report.low_confidence[:10]:
            lines.append(f"[LOW] {vc.claim}")
        if report.contradictions:
            lines.append("\n=== CONTRADICTIONS ===")
            for c in report.contradictions[:5]:
                lines.append(f"CONFLICT: '{c['claim_a']}' vs '{c['claim_b']}'")
        return "\n".join(lines)

    def _call_llm(self, plan: ResearchPlan, claim_digest: str) -> dict[str, Any]:
        user_msg = (
            f"Topic: {plan.topic}\n"
            f"Subtopics: {', '.join(plan.subtopics)}\n\n"
            f"Evidence digest:\n{claim_digest}"
        )
        message = self._llm.messages.create(
            model=self._model,
            max_tokens=4096,
            system=_SYNTHESIS_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)


# ---------------------------------------------------------------------------
# Shared utility (avoid circular import — copy from verification_engine)
# ---------------------------------------------------------------------------

def _claims_are_similar(a: str, b: str, threshold: float = 0.2) -> bool:
    stop = {"the", "and", "for", "that", "with", "are", "was", "has"}

    def tok(t: str) -> set[str]:
        return set(re.findall(r"\b[a-z]{3,}\b", t.lower())) - stop

    ta, tb = tok(a), tok(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= threshold
