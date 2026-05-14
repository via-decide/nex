"""
Module 2 — Source Discovery

Discovers, filters, and ranks candidate URLs for a research plan.
Only open-access sources are accepted; paywall / login-gated URLs are rejected.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import anthropic
import httpx


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredSource:
    url: str
    title: str
    snippet: str
    source_type: str          # "wikipedia" | "arxiv" | "gov" | "engineering_blog" | "dataset" | "web"
    relevance_score: float    # 0.0 – 1.0
    is_open_access: bool
    domain: str = field(init=False)

    def __post_init__(self) -> None:
        self.domain = urlparse(self.url).netloc

    @property
    def uid(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Paywall / login-gate detection
# ---------------------------------------------------------------------------

_BLOCKED_DOMAINS: set[str] = {
    "jstor.org", "springer.com", "sciencedirect.com", "tandfonline.com",
    "wiley.com", "ieee.org", "acm.org", "nature.com", "science.org",
    "oup.com", "cambridge.org", "elsevier.com", "researchgate.net",
}

_OPEN_ACCESS_DOMAINS: set[str] = {
    "arxiv.org", "en.wikipedia.org", "plos.org", "pubmed.ncbi.nlm.nih.gov",
    "biorxiv.org", "medrxiv.org", "ssrn.com", "zenodo.org",
    "semanticscholar.org", "openreview.net", "hal.science",
}

_GOV_TLD_PATTERN = re.compile(r"\.(gov|mil|edu)$")
_SOURCE_TYPE_MAP: dict[str, str] = {
    "en.wikipedia.org": "wikipedia",
    "arxiv.org": "arxiv",
    "biorxiv.org": "arxiv",
    "medrxiv.org": "arxiv",
    "semanticscholar.org": "arxiv",
}


def _classify_source(url: str) -> str:
    domain = urlparse(url).netloc.lstrip("www.")
    if domain in _SOURCE_TYPE_MAP:
        return _SOURCE_TYPE_MAP[domain]
    if _GOV_TLD_PATTERN.search(domain):
        return "gov"
    if any(kw in domain for kw in ("github", "medium", "dev.to", "blog", "engineering")):
        return "engineering_blog"
    if any(kw in domain for kw in ("data", "dataset", "kaggle", "huggingface")):
        return "dataset"
    return "web"


def _is_open_access(url: str) -> bool:
    """Determine if a URL is open-access.

    Args:
        url: URL to evaluate.

    Returns:
        True when the URL is considered open-access.

    Raises:
        None.

    Notes:
        Uses pessimistic default: unknown domains are treated as paywalled
        unless explicitly allowlisted.
    """
    domain = urlparse(url).netloc.lstrip("www.")
    if domain in _OPEN_ACCESS_DOMAINS:
        return True
    if domain in _BLOCKED_DOMAINS:
        return False
    if _GOV_TLD_PATTERN.search(domain):
        return True
    return False  # pessimistic: require explicit allowlisting


# ---------------------------------------------------------------------------
# Wikipedia source discovery
# ---------------------------------------------------------------------------

_WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"


async def _wiki_search(client: httpx.AsyncClient, query: str, limit: int = 5) -> list[DiscoveredSource]:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "origin": "*",
    }
    resp = await client.get(_WIKI_SEARCH, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
        results.append(DiscoveredSource(
            url=url,
            title=title,
            snippet=snippet,
            source_type="wikipedia",
            relevance_score=0.8,
            is_open_access=True,
        ))
    return results


# ---------------------------------------------------------------------------
# arXiv source discovery
# ---------------------------------------------------------------------------

_ARXIV_SEARCH = "https://export.arxiv.org/api/query"


async def _arxiv_search(client: httpx.AsyncClient, query: str, limit: int = 10) -> list[DiscoveredSource]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    resp = await client.get(_ARXIV_SEARCH, params=params, timeout=15)
    resp.raise_for_status()
    text = resp.text

    entries = re.findall(r"<entry>(.*?)</entry>", text, re.DOTALL)
    results = []
    for entry in entries:
        title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        id_m = re.search(r"<id>(.*?)</id>", entry)
        summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        if not (title_m and id_m):
            continue
        title = title_m.group(1).strip().replace("\n", " ")
        url = id_m.group(1).strip()
        # Use abs URL (HTML page)
        url = url.replace("http://", "https://").replace("/pdf/", "/abs/")
        snippet = (summary_m.group(1).strip().replace("\n", " ") if summary_m else "")[:300]
        results.append(DiscoveredSource(
            url=url,
            title=title,
            snippet=snippet,
            source_type="arxiv",
            relevance_score=0.9,
            is_open_access=True,
        ))
    return results


# ---------------------------------------------------------------------------
# Semantic Scholar source discovery
# ---------------------------------------------------------------------------

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


async def _s2_search(client: httpx.AsyncClient, query: str, limit: int = 8) -> list[DiscoveredSource]:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,url,abstract,openAccessPdf",
    }
    resp = await client.get(_S2_SEARCH, params=params, timeout=15)
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for paper in data.get("data", []):
        oa = paper.get("openAccessPdf")
        if not oa:
            continue
        url = oa.get("url", paper.get("url", ""))
        if not url:
            continue
        results.append(DiscoveredSource(
            url=url,
            title=paper.get("title", ""),
            snippet=(paper.get("abstract") or "")[:300],
            source_type="arxiv",
            relevance_score=0.85,
            is_open_access=True,
        ))
    return results


# ---------------------------------------------------------------------------
# SourceDiscovery orchestrator
# ---------------------------------------------------------------------------

class SourceDiscovery:
    """
    Discover and rank sources for a research plan.

    Usage:
        discovery = SourceDiscovery()
        sources = await discovery.discover_sources(plan)
        ranked  = discovery.rank_sources(sources)
    """

    def __init__(self, max_sources: int = 60) -> None:
        self.max_sources = max_sources
        self._llm = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = "claude-haiku-4-5-20251001"

    async def discover_sources(
        self,
        queries: list[str],
        source_types: list[str] | None = None,
        event_callback: Any | None = None,
    ) -> list[DiscoveredSource]:
        """
        Run parallel searches across all enabled source types.

        Args:
            queries: Search queries from the ResearchPlan.
            source_types: Which source types to query. Defaults to all.
        """
        source_types = source_types or ["wikipedia", "arxiv", "semanticscholar"]
        all_sources: list[DiscoveredSource] = []
        capped_queries = queries[:10]

        async with httpx.AsyncClient(follow_redirects=True) as client:
            for query in capped_queries:
                query_sources = await self._discover_for_query(client, query, source_types)
                open_count = len([s for s in query_sources if s.is_open_access])
                retries = 0
                current_query = query
                while open_count < 3 and retries < 2:
                    retries += 1
                    current_query = await self._rephrase_query(current_query)
                    if event_callback:
                        event_callback(
                            "reformulation",
                            "Refining search...",
                            {"original_query": query, "refined_query": current_query, "retry": retries},
                        )
                    retry_sources = await self._discover_for_query(client, current_query, source_types)
                    query_sources.extend(retry_sources)
                    open_count = len([s for s in query_sources if s.is_open_access])
                all_sources.extend(query_sources)

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[DiscoveredSource] = []
        for src in all_sources:
            if src.url not in seen:
                seen.add(src.url)
                unique.append(src)

        # Filter out paywalled sources
        open_sources = [s for s in unique if s.is_open_access]
        return open_sources

    async def _discover_for_query(
        self,
        client: httpx.AsyncClient,
        query: str,
        source_types: list[str],
    ) -> list[DiscoveredSource]:
        tasks: list[asyncio.Task] = []
        if "wikipedia" in source_types:
            tasks.append(asyncio.create_task(_wiki_search(client, query, limit=5)))
        if "arxiv" in source_types:
            tasks.append(asyncio.create_task(_arxiv_search(client, query, limit=8)))
        if "semanticscholar" in source_types:
            tasks.append(asyncio.create_task(_s2_search(client, query, limit=6)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[DiscoveredSource] = []
        for result in results:
            if isinstance(result, list):
                merged.extend(result)
        return merged

    async def _rephrase_query(self, query: str) -> str:
        prompt = (
            "Rephrase this research query to improve open-access discoverability. "
            "Use a different angle/synonyms/specific terms. Return only the rewritten query.\n\n"
            f"Query: {query}"
        )
        try:
            message = await self._llm.messages.create(
                model=self._model,
                max_tokens=120,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip().split("\n")[0]
        except Exception:
            return query

    def rank_sources(
        self,
        sources: list[DiscoveredSource],
        keywords: list[str] | None = None,
    ) -> list[DiscoveredSource]:
        """
        Rank sources by relevance.

        Ranking factors:
        - source_type weight (arxiv > wikipedia > gov > web > blog)
        - keyword presence in title/snippet
        - base relevance_score
        """
        type_weights: dict[str, float] = {
            "arxiv": 1.0,
            "wikipedia": 0.85,
            "gov": 0.80,
            "dataset": 0.75,
            "engineering_blog": 0.65,
            "web": 0.55,
        }
        keywords = [kw.lower() for kw in (keywords or [])]

        def _score(src: DiscoveredSource) -> float:
            base = src.relevance_score * type_weights.get(src.source_type, 0.5)
            if keywords:
                text = (src.title + " " + src.snippet).lower()
                hits = sum(1 for kw in keywords if kw in text)
                base += 0.05 * hits
            return min(base, 1.0)

        return sorted(sources, key=_score, reverse=True)[: self.max_sources]
