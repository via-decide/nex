#!/usr/bin/env python3
"""
core/fused_rag.py — Zayvora Fused RAG Orchestrator.
Fuses multiple research and engineering knowledge sources into a single,
lineage-aware context for Zayvora.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Dict

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASE_CORPUS_DIR = Path("/Users/dharamdaxini/Downloads/via/nex_repo/corpus/software")
LINEAGE_DIR = BASE_CORPUS_DIR / "software_lineage"
EMERGENCE_DIR = BASE_CORPUS_DIR / "software_emergence_maps"
PRESSURE_DIR = BASE_CORPUS_DIR / "software_continuity_pressure"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("FusedRAG")

@dataclass
class FusedContextItem:
    source: str
    content: Any
    relevance: float
    source_type: str  # "lineage" | "pressure" | "emergence" | "research"
    metadata: Dict[str, Any] = field(default_factory=dict)

class FusedRAG:
    def __init__(self):
        self.indices = {
            "lineage": list(LINEAGE_DIR.glob("*.json")),
            "emergence": list(EMERGENCE_DIR.glob("*.json")),
            "pressure": list(PRESSURE_DIR.glob("*.json"))
        }

    def _simple_search(self, query: str, files: List[Path]) -> List[FusedContextItem]:
        results = []
        query_terms = set(query.lower().split())
        
        for file_path in files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    content_str = json.dumps(data).lower()
                    
                    # Basic keyword overlap relevance
                    matches = sum(1 for term in query_terms if term in content_str)
                    if matches > 0:
                        relevance = matches / len(query_terms)
                        results.append(FusedContextItem(
                            source=file_path.name,
                            content=data,
                            relevance=relevance,
                            source_type=file_path.parent.name
                        ))
            except Exception as e:
                log.warning(f"Failed to read {file_path}: {e}")
        
        return sorted(results, key=lambda x: x.relevance, reverse=True)

    async def query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        log.info(f"Fused RAG Query: {query}")
        
        all_results = []
        all_results.extend(self._simple_search(query, self.indices["lineage"]))
        all_results.extend(self._simple_search(query, self.indices["emergence"]))
        all_results.extend(self._simple_search(query, self.indices["pressure"]))
        
        # Deduplicate and sort
        fused = sorted(all_results, key=lambda x: x.relevance, reverse=True)[:limit]
        
        return {
            "query": query,
            "fused_context": [
                {
                    "source": item.source,
                    "type": item.source_type,
                    "relevance": round(item.relevance, 2),
                    "data": item.content
                } for item in fused
            ],
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_sources_scanned": sum(len(v) for v in self.indices.values()),
                "fused_count": len(fused)
            }
        }

# ---------------------------------------------------------------------------
# CLI / ENTRY
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    rag = FusedRAG()
    async def test():
        res = await rag.query("vscode architecture plugin evolution")
        print(json.dumps(res, indent=2))
    asyncio.run(test())
