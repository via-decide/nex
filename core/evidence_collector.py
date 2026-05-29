"""
Module 3 — Evidence Collector

Fetches each source URL, extracts structured text, and produces an
EvidenceItem with key claims and citations. Uses local Zayvora/Ollama
inference to extract structured evidence from raw page text.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .source_discovery import DiscoveredSource
from .llm_client import LocalLLMClient


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


async def _llm_extract(client: LocalLLMClient, text: str, url: str) -> dict[str, Any]:
    """Map-reduce extract structured evidence from raw page text with a local model."""
    async def _extract_chunk(chunk: str, idx: int) -> dict[str, Any]:
        content = f"Source URL: {url}\nChunk: {idx}\n\nText:\n{_truncate(chunk)}"
        return await client.generate_json(content, system=_EXTRACT_SYSTEM, max_tokens=1024)

    try:
        chunks = [text[i:i + 5500] for i in range(0, len(text), 5500)][:8]
        mapped = await asyncio.gather(*[_extract_chunk(chunk, i + 1) for i, chunk in enumerate(chunks)])
        claims: list[str] = []
        citations: list[str] = []
        summaries: list[str] = []
        confidence = 0.0
        published_at = None
        for item in mapped:
            summaries.append(item.get("summary", ""))
            claims.extend(item.get("key_claims", []))
            citations.extend(item.get("citations", []))
            published_at = published_at or item.get("published_at")
            confidence = max(confidence, float(item.get("extraction_confidence", 0.0) or 0.0))
        return {
            "summary": " ".join(s for s in summaries if s)[:1000],
            "key_claims": list(dict.fromkeys(claims))[:12],
            "citations": list(dict.fromkeys(citations + _extract_urls(text)))[:10],
            "published_at": published_at,
            "extraction_confidence": confidence,
        }
    except json.JSONDecodeError as exc:
        print(f"[EvidenceCollector._llm_extract] JSON parse error from {url}: {exc}")
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
        model: str | None = None,
        concurrency: int = 8,
    ) -> None:
        self._llm = LocalLLMClient(model=model)
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

                # Map-reduce extraction keeps each local-model prompt within context limits.
                extracted = await _llm_extract(self._llm, text, src.url)

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
