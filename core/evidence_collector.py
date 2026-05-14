"""
Module 3 — Evidence Collector

Fetches each source URL, extracts structured text, and produces an
EvidenceItem with key claims and citations. Uses Claude to extract
structured evidence from raw page text.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx

from .source_discovery import DiscoveredSource


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    evidence_item_id: str
    source_url: str
    source_title: str
    source_type: str
    summary: str
    key_claims: list[str]
    citations: list[str]
    raw_text_length: int
    extraction_confidence: float   # 0.0 – 1.0
    published_at: str | None = None
    contradiction_pairs: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def claim_count(self) -> int:
        return len(self.key_claims)


# ---------------------------------------------------------------------------
# Text cleaning helpers
# ---------------------------------------------------------------------------

def _clean_html(html: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate(text: str, max_chars: int = 6000) -> str:
    return text[:max_chars] if len(text) > max_chars else text


def _extract_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s\"'>]+")
    return list(set(pattern.findall(text)))[:20]


# ---------------------------------------------------------------------------
# Wikipedia fast-path extractor
# ---------------------------------------------------------------------------

_WIKI_API = "https://en.wikipedia.org/w/api.php"


async def _fetch_wikipedia(client: httpx.AsyncClient, url: str) -> str:
    """Use Wikipedia API for clean text extraction."""
    title = url.rstrip("/").split("/wiki/")[-1].replace("_", " ")
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json",
        "origin": "*",
    }
    resp = await client.get(_WIKI_API, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        return page.get("extract", "")
    return ""


# ---------------------------------------------------------------------------
# Generic HTTP page fetcher
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "NexResearchBot/1.0 (research-automation; "
        "contact: research@nex.ai)"
    )
}


async def _fetch_generic(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    ct = resp.headers.get("content-type", "")
    if "html" in ct:
        return _clean_html(resp.text)
    return resp.text


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """You are a research evidence extractor. Given raw text from a source,
extract structured evidence in JSON. Return ONLY valid JSON.

Schema:
{
  "summary": "<2-4 sentence neutral summary of the source>",
  "key_claims": ["<factual claim 1>", ...],  // 3-10 specific, verifiable claims
  "citations": ["<reference or URL mentioned in text>", ...],  // up to 10
  "published_at": "<ISO date string if available, else null>",
  "extraction_confidence": <0.0-1.0>  // how clearly the text supports extraction
}

Rules:
- Claims must be specific and factual (not opinions).
- Each claim should be a single, complete sentence.
- Do not invent information not present in the text.
- Extract publication date if present via metadata tags, byline, DOI/arXiv history, or visible date strings.
- extraction_confidence: 1.0 = clear academic text, 0.5 = general web, 0.2 = noisy/irrelevant.
"""


def _llm_extract(client: anthropic.Anthropic, model: str, text: str, url: str) -> dict[str, Any]:
    """Extract structured evidence from raw page text.

    Args:
        client: Anthropic client instance.
        model: Model name to use for extraction.
        text: Raw source text to parse.
        url: Source URL used for debugging context.

    Returns:
        Dict with keys: summary, key_claims, citations, extraction_confidence.
        Returns default empty values on parsing or runtime failures.

    Raises:
        None.
    """
    try:
        content = f"Source URL: {url}\n\nText:\n{_truncate(text)}"
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[EvidenceCollector._llm_extract] JSON parse error from {url}: {exc}")
        return {
            "summary": "",
            "key_claims": [],
            "citations": [],
            "published_at": None,
            "extraction_confidence": 0.0,
        }
    except Exception as exc:
        print(f"[EvidenceCollector._llm_extract] Unexpected error from {url}: {exc}")
        return {
            "summary": "",
            "key_claims": [],
            "citations": [],
            "published_at": None,
            "extraction_confidence": 0.0,
        }


# ---------------------------------------------------------------------------
# Evidence Collector
# ---------------------------------------------------------------------------

class EvidenceCollector:
    """
    Collect and extract structured evidence from a list of sources.

    Usage:
        collector = EvidenceCollector()
        evidence = await collector.collect(sources)
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",  # fast model for bulk extraction
        concurrency: int = 8,
    ) -> None:
        self._llm = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model
        self._sem = asyncio.Semaphore(concurrency)

    async def collect(
        self,
        sources: list[DiscoveredSource],
        max_sources: int = 50,
    ) -> list[EvidenceItem]:
        """Fetch and extract evidence from up to max_sources sources."""
        targets = sources[:max_sources]
        async with httpx.AsyncClient(follow_redirects=True) as http:
            tasks = [
                asyncio.create_task(self._process(http, src))
                for src in targets
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        evidence: list[EvidenceItem] = []
        for r in results:
            if isinstance(r, EvidenceItem):
                evidence.append(r)
        return evidence

    async def _process(
        self, http: httpx.AsyncClient, src: DiscoveredSource
    ) -> EvidenceItem | None:
        async with self._sem:
            try:
                # Fetch raw text
                if "wikipedia.org" in src.url:
                    text = await _fetch_wikipedia(http, src.url)
                else:
                    text = await _fetch_generic(http, src.url)

                if not text or len(text) < 100:
                    return None

                # LLM extraction (sync Anthropic client, run in thread)
                loop = asyncio.get_event_loop()
                extracted = await loop.run_in_executor(
                    None, _llm_extract, self._llm, self._model, text, src.url
                )

                # Safely convert extraction_confidence to float
                try:
                    conf = float(extracted.get("extraction_confidence", 0.5))
                    # Clamp to valid range
                    conf = max(0.0, min(1.0, conf))
                except (ValueError, TypeError):
                    print(f"[EvidenceCollector._process] Invalid confidence value from {src.url}")
                    conf = 0.5

                return EvidenceItem(
                    evidence_item_id=src.uid,
                    source_url=src.url,
                    source_title=src.title,
                    source_type=src.source_type,
                    summary=extracted.get("summary", ""),
                    key_claims=extracted.get("key_claims", []),
                    citations=extracted.get("citations", []),
                    raw_text_length=len(text),
                    extraction_confidence=conf,
                    published_at=extracted.get("published_at"),
                    metadata={"domain": src.domain},
                )

            except Exception as exc:
                # Log but don't crash the pipeline
                print(f"[EvidenceCollector] Failed {src.url}: {exc}")
                return None
