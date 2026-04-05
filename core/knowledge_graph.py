"""
Module 5 — Knowledge Graph Builder

Constructs a directed concept graph from verified claims and evidence.
Each node is a concept; edges represent relationships discovered via
LLM analysis. Exports to JSON and Mermaid diagram format.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .verification_engine import VerificationReport, VerifiedClaim, Confidence


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    id: str           # slug identifier
    label: str        # human-readable label
    node_type: str    # "concept" | "finding" | "source" | "entity"
    confidence: str   # mirrors Confidence enum value
    description: str
    claims: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str     # e.g. "impacts", "requires", "improves", "contradicts"
    weight: float     # 0.0–1.0


@dataclass
class KnowledgeGraphData:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    root_topic: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_topic": self.root_topic,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "type": n.node_type,
                    "confidence": n.confidence,
                    "description": n.description,
                    "claims": n.claims,
                    "sources": n.sources,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "relation": e.relation,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self.nodes:
            safe_id = node.id.replace("-", "_")
            label = node.label.replace('"', "'")
            shape = f'["{label}"]' if node.node_type == "concept" else f'("{label}")'
            lines.append(f"    {safe_id}{shape}")
        for edge in self.edges:
            src = edge.source_id.replace("-", "_")
            tgt = edge.target_id.replace("-", "_")
            label = edge.relation.replace('"', "'")
            lines.append(f"    {src} -->|{label}| {tgt}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


# ---------------------------------------------------------------------------
# LLM relationship extractor
# ---------------------------------------------------------------------------

_RELATION_SYSTEM = """You are a knowledge graph builder. Given a list of research claims,
extract concept nodes and relationships in JSON. Return ONLY valid JSON.

Schema:
{
  "concepts": [
    {"id": "<slug>", "label": "<short concept name>", "description": "<1-sentence>"}
  ],
  "relationships": [
    {"source": "<concept id>", "target": "<concept id>", "relation": "<verb phrase>", "weight": 0.0-1.0}
  ]
}

Rules:
- Extract 5-15 concepts. Each concept is a key technical entity or idea.
- Relations must be directed and use simple verb phrases (improves, requires, enables, reduces, etc.).
- Weight indicates strength of relationship (0.9 = strong, 0.4 = weak).
- Use only concept IDs that appear in the concepts list.
"""


class KnowledgeGraph:
    """
    Build a knowledge graph from a VerificationReport.

    Usage:
        kg = KnowledgeGraph()
        graph = kg.build(report, topic="V2X Communication")
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._llm = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model

    def build(
        self,
        report: VerificationReport,
        topic: str = "Research Topic",
    ) -> KnowledgeGraphData:
        """
        Extract concepts and relationships, return a KnowledgeGraphData.
        """
        # Use high-confidence claims for graph construction
        claims = [vc.claim for vc in report.high_confidence_claims[:40]]
        if not claims:
            claims = [vc.claim for vc in report.low_confidence][:20]

        raw = self._extract_graph(claims, topic)
        return self._build_graph_data(raw, report, topic)

    def _extract_graph(self, claims: list[str], topic: str) -> dict[str, Any]:
        claim_text = "\n".join(f"- {c}" for c in claims[:40])
        user_msg = f"Topic: {topic}\n\nClaims:\n{claim_text}"
        message = self._llm.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_RELATION_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def _build_graph_data(
        self,
        raw: dict[str, Any],
        report: VerificationReport,
        topic: str,
    ) -> KnowledgeGraphData:
        # Build confidence map from claims
        claim_confidence: dict[str, str] = {}
        for vc in report.all_claims:
            key = vc.claim[:60].lower()
            claim_confidence[key] = vc.confidence.value

        nodes: list[GraphNode] = []
        node_ids: set[str] = set()

        for concept in raw.get("concepts", []):
            nid = concept.get("id") or _slug(concept.get("label", "unknown"))
            if nid in node_ids:
                continue
            node_ids.add(nid)
            nodes.append(GraphNode(
                id=nid,
                label=concept.get("label", nid),
                node_type="concept",
                confidence=Confidence.LIKELY.value,
                description=concept.get("description", ""),
            ))

        # Add root topic node
        root_id = _slug(topic)
        if root_id not in node_ids:
            nodes.insert(0, GraphNode(
                id=root_id,
                label=topic,
                node_type="entity",
                confidence=Confidence.VERIFIED.value,
                description=f"Root research topic: {topic}",
            ))
            node_ids.add(root_id)

        edges: list[GraphEdge] = []
        for rel in raw.get("relationships", []):
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            if src not in node_ids or tgt not in node_ids:
                continue
            edges.append(GraphEdge(
                source_id=src,
                target_id=tgt,
                relation=rel.get("relation", "relates-to"),
                weight=float(rel.get("weight", 0.5)),
            ))

        return KnowledgeGraphData(nodes=nodes, edges=edges, root_topic=topic)
