"""
Module 1 — Research Planner

Breaks a research question into structured subtopics, keywords, and a
prioritised research strategy using the local Zayvora/Ollama model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .llm_client import LocalLLMClient


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResearchPlan:
    topic: str
    subtopics: list[str]
    keywords: list[str]
    search_queries: list[str]
    source_types: list[str]
    depth: str                      # "standard" | "deep" | "exhaustive"
    estimated_sources: int
    strategy_notes: str
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert research strategist. Given a research question
you produce a precise, structured research plan in JSON. Return ONLY valid JSON.

The JSON schema is:
{
  "topic": "<concise topic label>",
  "subtopics": ["<subtopic 1>", ...],          // 3-8 subtopics
  "keywords": ["<keyword 1>", ...],            // 8-20 search keywords
  "search_queries": ["<query 1>", ...],        // 5-15 concrete search queries
  "source_types": ["wikipedia", "arxiv", "gov", "engineering_blog", "dataset", ...],
  "depth": "standard" | "deep" | "exhaustive",
  "estimated_sources": <integer 10-100>,
  "strategy_notes": "<brief paragraph on research approach>"
}

Rules:
- Keywords must be specific and varied (acronyms, technical terms, synonyms).
- Search queries must be ready to feed directly into a search engine.
- depth is "standard" for general questions, "deep" for technical/academic topics,
  "exhaustive" for comprehensive literature reviews.
- estimated_sources: standard=10-30, deep=30-60, exhaustive=60-100.
"""


class ResearchPlanner:
    """
    Decomposes a user research question into a structured ResearchPlan.

    Usage:
        planner = ResearchPlanner()
        plan = await planner.plan("How do Vehicle-to-Infrastructure systems work?")
    """

    def __init__(self, model: str | None = None) -> None:
        self._client = LocalLLMClient(model=model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def plan(self, question: str, depth_hint: str = "auto") -> ResearchPlan:
        """
        Generate a ResearchPlan for the given question.

        Args:
            question: Natural-language research question from the user.
            depth_hint: "standard" | "deep" | "exhaustive" | "auto"
        """
        raw = await self._call_llm(question, depth_hint)
        return self._parse(raw)

    def plan_sync(self, question: str, depth_hint: str = "auto") -> ResearchPlan:
        """Synchronous wrapper around plan()."""
        raw = self._call_llm_sync(question, depth_hint)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _call_llm(self, question: str, depth_hint: str) -> dict[str, Any]:
        user_content = f"Research question: {question}"
        if depth_hint != "auto":
            user_content += f"\nPreferred depth: {depth_hint}"
        return await self._client.generate_json(user_content, system=SYSTEM_PROMPT, max_tokens=1024)

    def _call_llm_sync(self, question: str, depth_hint: str) -> dict[str, Any]:
        user_content = f"Research question: {question}"
        if depth_hint != "auto":
            user_content += f"\nPreferred depth: {depth_hint}"
        return self._client.generate_json_sync(user_content, system=SYSTEM_PROMPT, max_tokens=1024)

    def _parse(self, raw: dict[str, Any]) -> ResearchPlan:
        return ResearchPlan(
            topic=raw.get("topic", "Unknown Topic"),
            subtopics=raw.get("subtopics", []),
            keywords=raw.get("keywords", []),
            search_queries=raw.get("search_queries", []),
            source_types=raw.get("source_types", ["wikipedia", "arxiv", "web"]),
            depth=raw.get("depth", "standard"),
            estimated_sources=int(raw.get("estimated_sources", 20)),
            strategy_notes=raw.get("strategy_notes", ""),
            raw=raw,
        )


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import sys

    async def _main() -> None:
        q = " ".join(sys.argv[1:]) or "How do Vehicle-to-Infrastructure systems work?"
        planner = ResearchPlanner()
        plan = await planner.plan(q)
        print(json.dumps(
            {
                "topic": plan.topic,
                "subtopics": plan.subtopics,
                "keywords": plan.keywords,
                "search_queries": plan.search_queries,
                "depth": plan.depth,
                "estimated_sources": plan.estimated_sources,
                "strategy_notes": plan.strategy_notes,
            },
            indent=2,
        ))

    asyncio.run(_main())
