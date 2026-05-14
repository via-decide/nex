#!/usr/bin/env python3
"""
scripts/harvest_software_ecosystems.py — Deterministic Software Systems Harvester.
Automates harvesting of technical papers, documentation, and blog posts
related to software civilizations, runtimes, and developer tooling.
"""

import os
import asyncio
import hashlib
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASE_CORPUS_DIR = Path("/Users/dharamdaxini/Downloads/via/nex_repo/corpus/software")
RAW_DIR = BASE_CORPUS_DIR / "software_raw"
TEXT_DIR = BASE_CORPUS_DIR / "software_text"

PRIORITY_DOMAINS = [
    "VSCode architecture", "Electron internals", "Monaco editor",
    "browser rendering engines", "terminal systems", "runtime abstraction layers",
    "plugin architectures", "Git internals", "Docker evolution",
    "package managers", "build systems", "local-first tooling",
    "debugging systems", "orchestration pipelines", "save-state systems",
    "persistence layers", "offline sync", "local-first architectures",
    "deterministic workflows", "replayable editing systems"
]

ARXIV_API = "https://export.arxiv.org/api/query"
WIKI_API = "https://en.wikipedia.org/w/api.php"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

LOG_FILE = BASE_CORPUS_DIR / "harvest.log"
os.makedirs(BASE_CORPUS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(TEXT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger("SoftwareHarvester")

# ---------------------------------------------------------------------------
# CORE HARVESTER
# ---------------------------------------------------------------------------

class SoftwareHarvester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)

    async def close(self):
        await self.client.aclose()

    async def search_arxiv(self, query: str, limit: int = 10):
        log.info(f"Searching arXiv: {query}")
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
        }
        try:
            resp = await self.client.get(ARXIV_API, params=params)
            resp.raise_for_status()
            entries = re.findall(r"<entry>(.*?)</entry>", resp.text, re.DOTALL)
            results = []
            for entry in entries:
                title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                id_m = re.search(r"<id>(.*?)</id>", entry)
                summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                if title_m and id_m:
                    results.append({
                        "title": title_m.group(1).strip().replace("\n", " "),
                        "url": id_m.group(1).strip().replace("http://", "https://").replace("/pdf/", "/abs/"),
                        "snippet": (summary_m.group(1).strip().replace("\n", " ") if summary_m else ""),
                        "source": "arxiv"
                    })
            return results
        except Exception as e:
            log.error(f"arXiv search failed for {query}: {e}")
            return []

    async def search_wiki(self, query: str, limit: int = 5):
        log.info(f"Searching Wikipedia: {query}")
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
            "origin": "*",
        }
        try:
            resp = await self.client.get(WIKI_API, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("query", {}).get("search", []):
                title = item["title"]
                results.append({
                    "title": title,
                    "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "snippet": re.sub(r"<[^>]+>", "", item.get("snippet", "")),
                    "source": "wikipedia"
                })
            return results
        except Exception as e:
            log.error(f"Wiki search failed for {query}: {e}")
            return []

    def save_artifact(self, data: dict):
        url_hash = hashlib.sha256(data['url'].encode()).hexdigest()[:12]
        filename = f"{url_hash}.json"
        with open(RAW_DIR / filename, "w") as f:
            json.dump(data, f, indent=2)
        
        # Save as text for processing
        text_filename = f"{url_hash}.txt"
        with open(TEXT_DIR / text_filename, "w") as f:
            f.write(f"TITLE: {data['title']}\n")
            f.write(f"URL: {data['url']}\n")
            f.write(f"SOURCE: {data['source']}\n")
            f.write(f"SNIPPET: {data['snippet']}\n")
        log.debug(f"Saved: {data['title']}")

    async def harvest_all(self):
        log.info("Starting Software Civilization Harvesting...")
        total_found = 0
        for domain in PRIORITY_DOMAINS:
            arxiv_results = await self.search_arxiv(domain)
            wiki_results = await self.search_wiki(domain)
            
            combined = arxiv_results + wiki_results
            for item in combined:
                item['harvested_at'] = datetime.now(timezone.utc).isoformat()
                item['domain'] = domain
                self.save_artifact(item)
                total_found += 1
            
            # Small delay to respect rate limits
            await asyncio.sleep(1)
        
        log.info(f"Harvesting Complete. Total unique sources identified: {total_found}")

async def main():
    harvester = SoftwareHarvester()
    try:
        await harvester.harvest_all()
    finally:
        await harvester.close()

if __name__ == "__main__":
    asyncio.run(main())
