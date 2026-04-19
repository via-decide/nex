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
from .utils import claims_are_similar


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
    citation_chain: list["CitationLink"] = field(default_factory=list)
    stale_data_warning: bool = False
    stale_data_warning_text: str | None = None


@dataclass
class ExecutiveBrief:
    one_liner: str
    top_findings: list[str]
    confidence_bar: float
    word_count: int


@dataclass
class CitationLink:
    claim: str
    evidence_item_id: str
    source_url: str
    domain: str
    publication_date: str


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
    source_freshness_summary: dict[str, Any] | None = None
    executive_brief: ExecutiveBrief | None = None
    disputed_claims: list[dict[str, Any]] = field(default_factory=list)
    hallucination_score: float | None = None

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
                    "citation_chain": [
                        {
                            "claim": c.claim,
                            "evidence_item_id": c.evidence_item_id,
                            "source_url": c.source_url,
                            "domain": c.domain,
                            "publication_date": c.publication_date,
                        }
                        for c in f.citation_chain
                    ],
                    "stale_data_warning": f.stale_data_warning,
                    "stale_data_warning_text": f.stale_data_warning_text,
                }
                for f in self.key_findings
            ],
            "evidence_sections": self.evidence_sections,
            "limitations": self.limitations,
            "future_research": self.future_research,
            "sources": self.sources,
            "knowledge_graph": self.knowledge_graph.to_dict(),
            "source_freshness_summary": self.source_freshness_summary,
            "executive_brief": (
                {
                    "one_liner": self.executive_brief.one_liner,
                    "top_findings": self.executive_brief.top_findings,
                    "confidence_bar": self.executive_brief.confidence_bar,
                    "word_count": self.executive_brief.word_count,
                }
                if self.executive_brief else None
            ),
            "disputed_claims": self.disputed_claims,
            "hallucination_score": self.hallucination_score,
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
            badge = {"VERIFIED": "✓", "LIKELY": "~", "CONTRADICTED": "!", "LOW_CONFIDENCE": "?"}[f.confidence]
            lines.append(f"### {i}. {f.headline}  `[{badge} {f.confidence}]`\n")
            lines.append(f.detail + "\n")
            if f.supporting_sources:
                src_list = "  ".join(f"[{j+1}]({u})" for j, u in enumerate(f.supporting_sources[:3]))
                lines.append(f"*Sources:* {src_list}\n")
        lines.append("## Evidence Sections\n")
        for section in self.evidence_sections:
            lines.append(f"### {section.get('title', 'Section')}\n")
            lines.append(section.get("content", "") + "\n")
        if self.disputed_claims:
            lines.append("## Disputed Claims\n")
            for item in self.disputed_claims:
                lines.append(
                    f"- **Conflict:** {item.get('claim_a', '')} ↔ {item.get('claim_b', '')}  "
                    f"(sources: {item.get('source_a', '')}, {item.get('source_b', '')})"
                )
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
  "future_research": ["<specific research direction 1>", ...],  // 4-8 items
  "executive_brief": {
    "one_liner": "<single sentence answer summary>",
    "top_findings": ["<plain english finding>", "<finding>", "<finding>"],
    "confidence_bar": <0.0-1.0>,
    "word_count": <int total words in full report body>
  }
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
        evidence_items: list[dict[str, Any]] | list[Any] | None = None,
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
        evidence_items = evidence_items or []
        evidence_by_url: dict[str, Any] = {
            item.source_url: item for item in evidence_items if getattr(item, "source_url", None)
        }

        for i, f in enumerate(raw.get("key_findings", []), 1):
            headline = f.get("headline", "")
            # Match confidence from verification
            conf = Confidence.LOW_CONFIDENCE.value
            matched_sources: list[str] = []
            for vc_claim in verification_report.all_claims:
                if claims_are_similar(headline, vc_claim.claim):
                    conf = vc_claim.confidence.value
                    matched_sources = vc_claim.supporting_sources[:3]
                    break

            citation_chain: list[CitationLink] = []
            stale_count = 0
            dated_count = 0
            for src in matched_sources:
                ev = evidence_by_url.get(src)
                domain = src.split("/")[2] if "://" in src else ""
                published_at = getattr(ev, "published_at", None) if ev else None
                if published_at:
                    dated_count += 1
                    if self._is_stale(published_at):
                        stale_count += 1
                citation_chain.append(CitationLink(
                    claim=headline,
                    evidence_item_id=getattr(ev, "evidence_item_id", ""),
                    source_url=src,
                    domain=domain,
                    publication_date=published_at or "",
                ))

            stale_data_warning = dated_count > 0 and (stale_count / dated_count) >= 0.5
            stale_data_warning_text = (
                "Most dated sources for this finding are over two years old; validate with newer evidence."
                if stale_data_warning else None
            )

            findings.append(ResearchFinding(
                id=f"finding-{i}",
                headline=headline,
                detail=f.get("detail", ""),
                confidence=conf,
                supporting_sources=matched_sources,
                related_concepts=f.get("related_concepts", []),
                subchat_seed=f.get("subchat_seed", f"Tell me more about: {headline}"),
                citation_chain=citation_chain,
                stale_data_warning=stale_data_warning,
                stale_data_warning_text=stale_data_warning_text,
            ))

        source_freshness_summary = self._build_source_freshness_summary(evidence_items)
        executive_brief_raw = raw.get("executive_brief", {})
        executive_brief = ExecutiveBrief(
            one_liner=executive_brief_raw.get("one_liner", ""),
            top_findings=executive_brief_raw.get("top_findings", [])[:3],
            confidence_bar=float(executive_brief_raw.get("confidence_bar", self._avg_confidence(findings))),
            word_count=int(executive_brief_raw.get("word_count", self._estimate_word_count(raw))),
        )

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
            source_freshness_summary=source_freshness_summary,
            executive_brief=executive_brief,
            disputed_claims=verification_report.contradictions,
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

    def _is_stale(self, published_at: str) -> bool:
        try:
            date_part = published_at[:10]
            source_date = datetime.fromisoformat(date_part)
            return (datetime.utcnow() - source_date).days > 730
        except Exception:
            return False

    def _build_source_freshness_summary(self, evidence_items: list[Any]) -> dict[str, Any]:
        total = len(evidence_items)
        dated = 0
        stale = 0
        for item in evidence_items:
            published_at = getattr(item, "published_at", None)
            if not published_at:
                continue
            dated += 1
            if self._is_stale(published_at):
                stale += 1
        return {
            "total_sources": total,
            "sources_with_dates": dated,
            "stale_sources": stale,
            "fresh_sources": max(dated - stale, 0),
        }

    def _avg_confidence(self, findings: list[ResearchFinding]) -> float:
        mapping = {
            Confidence.VERIFIED.value: 1.0,
            Confidence.LIKELY.value: 0.75,
            Confidence.CONTRADICTED.value: 0.35,
            Confidence.LOW_CONFIDENCE.value: 0.2,
        }
        if not findings:
            return 0.0
        return round(sum(mapping.get(f.confidence, 0.2) for f in findings) / len(findings), 3)

    def _estimate_word_count(self, raw: dict[str, Any]) -> int:
        chunks = [
            raw.get("executive_summary", ""),
            " ".join(f.get("detail", "") for f in raw.get("key_findings", [])),
            " ".join(s.get("content", "") for s in raw.get("evidence_sections", [])),
            raw.get("limitations", ""),
            " ".join(raw.get("future_research", [])),
        ]
        return len(" ".join(chunks).split())

    def _call_llm(self, plan: ResearchPlan, claim_digest: str) -> dict[str, Any]:
        """Call LLM to synthesize research report from evidence digest.

        Args:
            plan: Research plan metadata including topic and subtopics.
            claim_digest: Normalized digest of verified and contradictory claims.

        Returns:
            Dict with keys: title, executive_summary, key_findings,
            evidence_sections, limitations, future_research.

        Raises:
            None.
        """
        try:
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
        except json.JSONDecodeError as exc:
            print(f"[ResearchSynthesizer._call_llm] JSON parse error: {exc}")
            return {
                "title": f"Research Report: {plan.topic}",
                "executive_summary": "Report generation failed due to LLM response parsing error.",
                "key_findings": [],
                "evidence_sections": [],
                "limitations": "Pipeline encountered an error during synthesis.",
                "future_research": [],
            }
        except Exception as exc:
            print(f"[ResearchSynthesizer._call_llm] Unexpected error: {exc}")
            return {
                "title": f"Research Report: {plan.topic}",
                "executive_summary": "Report generation failed.",
                "key_findings": [],
                "evidence_sections": [],
                "limitations": "Pipeline encountered an unexpected error.",
                "future_research": [],
            }
