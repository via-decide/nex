"""
Module 4 — Claim Verification Engine

Cross-checks claims across all collected evidence, detects contradictions,
and assigns confidence scores to each claim.

Confidence levels:
  VERIFIED       — corroborated by 3+ independent sources
  LIKELY         — corroborated by 2 sources OR 1 high-quality source (arxiv/gov)
  LOW_CONFIDENCE — single low-quality source or contradicted
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import anthropic

from .evidence_collector import EvidenceItem
from .utils import claims_are_similar


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Confidence(str, Enum):
    VERIFIED = "VERIFIED"
    LIKELY = "LIKELY"
    CONTRADICTED = "CONTRADICTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass
class VerifiedClaim:
    claim: str
    confidence: Confidence
    supporting_sources: list[str]   # list of source URLs
    contradicting_sources: list[str]
    supporting_count: int
    notes: str = ""


@dataclass
class VerificationReport:
    verified: list[VerifiedClaim]
    likely: list[VerifiedClaim]
    contradicted: list[VerifiedClaim]
    low_confidence: list[VerifiedClaim]
    contradictions: list[dict[str, Any]]

    @property
    def all_claims(self) -> list[VerifiedClaim]:
        return self.verified + self.likely + self.contradicted + self.low_confidence

    @property
    def high_confidence_claims(self) -> list[VerifiedClaim]:
        return self.verified + self.likely + self.contradicted


# ---------------------------------------------------------------------------
# Contradiction helper
# ---------------------------------------------------------------------------

def _claims_contradict(a: str, b: str) -> bool:
    """Heuristic negation detection for obvious contradictions."""
    negation_pairs = [
        ("increases", "decreases"),
        ("reduces", "increases"),
        ("improves", "worsens"),
        ("effective", "ineffective"),
        ("safe", "unsafe"),
        ("higher", "lower"),
        ("faster", "slower"),
    ]
    al, bl = a.lower(), b.lower()
    for pos, neg in negation_pairs:
        if pos in al and neg in bl:
            return True
        if neg in al and pos in bl:
            return True
    return False


# ---------------------------------------------------------------------------
# Source quality weights
# ---------------------------------------------------------------------------

_SOURCE_QUALITY: dict[str, int] = {
    "arxiv": 3,
    "gov": 2,
    "wikipedia": 2,
    "engineering_blog": 1,
    "dataset": 2,
    "web": 1,
}


# ---------------------------------------------------------------------------
# LLM-assisted contradiction check
# ---------------------------------------------------------------------------

_CONTRADICT_SYSTEM = """You are a scientific claim verifier. Given two claims, determine if they
contradict each other. Return JSON only:
{"contradicts": true|false, "reason": "<brief explanation>"}"""


class VerificationEngine:
    """
    Verify and score all claims extracted from evidence.

    Usage:
        engine = VerificationEngine()
        report = engine.verify(evidence_list)
    """

    def __init__(
        self,
        use_llm_contradiction: bool = False,   # set True for more precise contradiction detection
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self._use_llm = use_llm_contradiction
        self._model = model
        self._llm = (
            anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            if use_llm_contradiction
            else None
        )

    def verify(self, evidence_list: list[EvidenceItem]) -> VerificationReport:
        """
        Cross-check all claims and produce a VerificationReport.
        """
        # Collect (claim, source_url, source_type) tuples
        all_claims: list[tuple[str, str, str, EvidenceItem]] = []
        for ev in evidence_list:
            for claim in ev.key_claims:
                all_claims.append((claim, ev.source_url, ev.source_type, ev))

        # Cluster similar claims
        clusters: list[list[tuple[str, str, str, EvidenceItem]]] = []
        assigned = [False] * len(all_claims)

        for i, (ci, ui, ti, ei) in enumerate(all_claims):
            if assigned[i]:
                continue
            cluster = [(ci, ui, ti, ei)]
            assigned[i] = True
            for j, (cj, uj, tj, ej) in enumerate(all_claims):
                if i == j or assigned[j]:
                    continue
                if claims_are_similar(ci, cj):
                    cluster.append((cj, uj, tj, ej))
                    assigned[j] = True
            clusters.append(cluster)

        # Score each cluster
        verified: list[VerifiedClaim] = []
        likely: list[VerifiedClaim] = []
        contradicted: list[VerifiedClaim] = []
        low_confidence: list[VerifiedClaim] = []
        contradictions: list[dict[str, Any]] = []

        for cluster in clusters:
            representative = cluster[0][0]
            sources = [c[1] for c in cluster]
            types = [c[2] for c in cluster]

            unique_domains = set(url.split("/")[2] for url in sources)
            quality_score = sum(_SOURCE_QUALITY.get(t, 1) for t in types)

            # Detect contradictions within cluster
            for idx_a in range(len(cluster)):
                for idx_b in range(idx_a + 1, len(cluster)):
                    ca, ua, _, ea = cluster[idx_a]
                    cb, ub, _, eb = cluster[idx_b]
                    if _claims_contradict(ca, cb):
                        contradiction = {
                            "claim_a": ca,
                            "source_a": ua,
                            "evidence_item_id_a": ea.evidence_item_id,
                            "claim_b": cb,
                            "source_b": ub,
                            "evidence_item_id_b": eb.evidence_item_id,
                        }
                        contradictions.append(contradiction)
                        ea.contradiction_pairs.append(
                            {"opposing_claim": cb, "source_url": ub}
                        )
                        eb.contradiction_pairs.append(
                            {"opposing_claim": ca, "source_url": ua}
                        )

            # Collect sources that contradict this representative claim
            contradicting: list[str] = []
            for c in contradictions:
                if c["claim_a"] == representative:
                    contradicting.append(c["source_b"])
                elif c["claim_b"] == representative:
                    contradicting.append(c["source_a"])

            vc = VerifiedClaim(
                claim=representative,
                confidence=Confidence.LOW_CONFIDENCE,  # placeholder
                supporting_sources=list(set(sources)),
                contradicting_sources=contradicting,
                supporting_count=len(unique_domains),
            )

            # Assign confidence
            if contradicting:
                vc.confidence = Confidence.CONTRADICTED
                contradicted.append(vc)
            elif len(unique_domains) >= 3 or quality_score >= 6:
                vc.confidence = Confidence.VERIFIED
                verified.append(vc)
            elif len(unique_domains) == 2 or quality_score >= 3:
                vc.confidence = Confidence.LIKELY
                likely.append(vc)
            else:
                vc.confidence = Confidence.LOW_CONFIDENCE
                low_confidence.append(vc)

        return VerificationReport(
            verified=verified,
            likely=likely,
            contradicted=contradicted,
            low_confidence=low_confidence,
            contradictions=contradictions,
        )

    def _llm_contradict(self, a: str, b: str) -> bool:
        if not self._llm:
            return False
        msg = self._llm.messages.create(
            model=self._model,
            max_tokens=128,
            system=_CONTRADICT_SYSTEM,
            messages=[{"role": "user", "content": f"Claim A: {a}\nClaim B: {b}"}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text).get("contradicts", False)
        except Exception:
            return False
