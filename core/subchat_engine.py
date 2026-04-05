"""
Module 9 — Subchat Engine

Each research finding becomes an interactive thread. Users can ask
follow-up questions, request citations, compare findings, or trigger
Zayvora simulations — all within the context of a specific finding.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator

import anthropic

from .research_synthesizer import ResearchFinding, ResearchReport


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubchatMessage:
    role: str        # "user" | "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubchatThread:
    thread_id: str
    finding_id: str
    finding_headline: str
    messages: list[SubchatMessage] = field(default_factory=list)
    zayvora_runs: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(finding: ResearchFinding, report: ResearchReport) -> str:
    sources_text = "\n".join(
        f"- {s}" for s in finding.supporting_sources[:5]
    )
    return f"""You are a focused research assistant for a specific finding within a larger research document.

Research document topic: {report.topic}

You are helping the user explore this specific finding:
"{finding.headline}"

Supporting detail: {finding.detail}

Confidence level: {finding.confidence}

Supporting sources:
{sources_text}

Related concepts: {', '.join(finding.related_concepts)}

Instructions:
- Answer questions specifically about this finding and its evidence
- When asked to explain a study, refer to the supporting sources
- When comparing research, highlight the confidence level differences
- If the user asks for a simulation or technical computation, prefix your response with [ZAYVORA_REQUEST] and describe what should be computed
- Be precise and cite evidence when making claims
- Acknowledge limitations and uncertainty where appropriate
"""


# ---------------------------------------------------------------------------
# Subchat Engine
# ---------------------------------------------------------------------------

class SubchatEngine:
    """
    Manage per-finding subchat threads with streaming support.

    Usage:
        engine = SubchatEngine(report)

        # Create a thread for a finding
        thread = engine.create_thread("finding-1")

        # Get a streaming response
        for chunk in engine.chat_stream(thread.thread_id, "Explain the key study"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        report: ResearchReport,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self._report = report
        self._model = model
        self._llm = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._threads: dict[str, SubchatThread] = {}
        self._findings: dict[str, ResearchFinding] = {
            f.id: f for f in report.key_findings
        }

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def create_thread(self, finding_id: str) -> SubchatThread:
        """Create a new subchat thread for a finding."""
        finding = self._findings.get(finding_id)
        if not finding:
            raise ValueError(f"Finding {finding_id!r} not found in report.")
        thread = SubchatThread(
            thread_id=str(uuid.uuid4()),
            finding_id=finding_id,
            finding_headline=finding.headline,
        )
        # Seed with suggested question
        if finding.subchat_seed:
            thread.messages.append(SubchatMessage(
                role="assistant",
                content=f"**Research finding loaded.** You might want to start by asking: *{finding.subchat_seed}*",
            ))
        self._threads[thread.thread_id] = thread
        return thread

    def get_thread(self, thread_id: str) -> SubchatThread | None:
        return self._threads.get(thread_id)

    def list_threads(self) -> list[SubchatThread]:
        return list(self._threads.values())

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(self, thread_id: str, user_message: str) -> str:
        """Send a message and return the full response."""
        return "".join(self.chat_stream(thread_id, user_message))

    def chat_stream(self, thread_id: str, user_message: str) -> Iterator[str]:
        """
        Send a message and stream the response token-by-token.
        Yields text chunks.
        """
        thread = self._threads.get(thread_id)
        if not thread:
            yield "Error: thread not found."
            return

        finding = self._findings[thread.finding_id]
        system = _build_system_prompt(finding, self._report)

        # Add user message to history
        thread.messages.append(SubchatMessage(role="user", content=user_message))

        # Build message history for API (skip seed assistant message)
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in thread.messages
            if m.role in ("user", "assistant")
            and not m.content.startswith("**Research finding loaded.**")
        ]

        # Stream
        full_response = ""
        with self._llm.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=api_messages,
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield text

        # Save assistant reply
        thread.messages.append(SubchatMessage(role="assistant", content=full_response))

        # Check for Zayvora simulation trigger
        if "[ZAYVORA_REQUEST]" in full_response:
            thread.zayvora_runs.append({
                "trigger_message": user_message,
                "zayvora_request": full_response,
                "status": "pending",
            })

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_citations(self, thread_id: str) -> list[str]:
        """Return all sources associated with the thread's finding."""
        thread = self._threads.get(thread_id)
        if not thread:
            return []
        finding = self._findings[thread.finding_id]
        return finding.supporting_sources

    def export_thread(self, thread_id: str) -> dict[str, Any]:
        """Serialise a thread for API response or storage."""
        thread = self._threads.get(thread_id)
        if not thread:
            return {}
        return {
            "thread_id": thread.thread_id,
            "finding_id": thread.finding_id,
            "finding_headline": thread.finding_headline,
            "created_at": thread.created_at,
            "messages": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in thread.messages
            ],
            "zayvora_runs": thread.zayvora_runs,
        }
