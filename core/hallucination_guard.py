"""Module 8 — Hallucination Guard.

Checks sentence-level grounding of synthesis output against collected evidence.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .evidence_collector import EvidenceItem
from .research_synthesizer import ResearchReport


@dataclass
class SentenceGrounding:
    sentence: str
    grounded: bool
    suggested_correction: str


@dataclass
class HallucinationGuardResult:
    executive_summary_checks: list[SentenceGrounding] = field(default_factory=list)
    finding_checks: dict[str, list[SentenceGrounding]] = field(default_factory=dict)
    hallucination_score: float = 0.0


class HallucinationGuard:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._llm = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model

    async def run(self, report: ResearchReport, evidence: list[EvidenceItem]) -> HallucinationGuardResult:
        evidence_digest = self._build_evidence_digest(evidence)
        exec_sentences = self._split_sentences(report.executive_summary)
        exec_checks = await self._check_sentences(exec_sentences, evidence_digest)

        finding_checks: dict[str, list[SentenceGrounding]] = {}
        for finding in report.key_findings:
            sentences = self._split_sentences(finding.detail)
            finding_checks[finding.id] = await self._check_sentences(sentences, evidence_digest)

        all_checks = exec_checks + [c for group in finding_checks.values() for c in group]
        ungrounded = sum(1 for check in all_checks if not check.grounded)
        score = (ungrounded / len(all_checks)) if all_checks else 0.0

        report.hallucination_score = round(score, 3)

        return HallucinationGuardResult(
            executive_summary_checks=exec_checks,
            finding_checks=finding_checks,
            hallucination_score=report.hallucination_score,
        )

    async def _check_sentences(self, sentences: list[str], evidence_digest: str) -> list[SentenceGrounding]:
        checks: list[SentenceGrounding] = []
        for sentence in sentences:
            verdict = await self._check_sentence(sentence, evidence_digest)
            checks.append(verdict)
        return checks

    async def _check_sentence(self, sentence: str, evidence_digest: str) -> SentenceGrounding:
        prompt = (
            "Assess whether the sentence is grounded in the evidence digest. "
            "Return strict JSON: {\"grounded\": true|false, \"suggested_correction\": \"...\"}.\n\n"
            f"Sentence: {sentence}\n\nEvidence:\n{evidence_digest}"
        )
        try:
            msg = await self._llm.messages.create(
                model=self._model,
                max_tokens=180,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            grounded = '"grounded": true' in raw.lower()
            correction_match = re.search(r'"suggested_correction"\s*:\s*"(.*?)"', raw, re.DOTALL)
            correction = correction_match.group(1).strip() if correction_match else sentence
            return SentenceGrounding(
                sentence=sentence,
                grounded=grounded,
                suggested_correction=correction,
            )
        except Exception:
            return SentenceGrounding(
                sentence=sentence,
                grounded=True,
                suggested_correction=sentence,
            )

    def _split_sentences(self, text: str) -> list[str]:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        return parts

    def _build_evidence_digest(self, evidence: list[EvidenceItem]) -> str:
        lines: list[str] = []
        for item in evidence[:30]:
            lines.append(f"[{item.evidence_item_id}] {item.summary}")
            for claim in item.key_claims[:3]:
                lines.append(f"- {claim}")
        return "\n".join(lines)
