"""
Nex Research UI — Backend API Server

Lightweight FastAPI wrapper that bridges the Nex research engine
to the Vite/React frontend. Delegates to the existing core pipeline
and adds simplified endpoints for the research UI.

Endpoints:
  POST /query          — run a research query
  GET  /sources        — list sources for a completed run
  GET  /status         — engine health and corpus stats
  GET  /query/stream   — SSE streaming for a research query
  POST /subchat        — follow-up chat on a finding
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Add project root to path so core imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.pipeline import DeepResearchPipeline, PipelineConfig, PipelineResult
from core.research_synthesizer import ResearchReport
from core.subchat_engine import SubchatEngine

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_runs: dict[str, dict[str, Any]] = {}
_results: dict[str, PipelineResult] = {}
_subchats: dict[str, SubchatEngine] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=2000)
    depth: str = Field("standard", pattern="^(standard|deep|exhaustive)$")
    max_sources: int = Field(30, ge=5, le=100)
    research_mode: bool = Field(
        True, description="Enable full research mode (Wikipedia, arXiv, etc.)"
    )
    source_types: list[str] = Field(
        default=["wikipedia", "arxiv", "semanticscholar"]
    )


class QueryResponse(BaseModel):
    run_id: str
    status: str
    answer: str | None = None
    sources: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    knowledge_graph: dict[str, Any] | None = None
    stats: dict[str, Any] = {}
    error: str | None = None


class SubchatRequest(BaseModel):
    run_id: str
    finding_id: str
    message: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Nex Research UI API starting on port 8000...")
    yield
    print("Nex Research UI API shutting down.")


app = FastAPI(
    title="Nex Research UI API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# POST /query — synchronous research query
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
async def run_query(request: QueryRequest) -> QueryResponse:
    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "status": "running",
        "question": request.query,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    source_types = request.source_types if request.research_mode else ["wikipedia"]
    config = PipelineConfig(
        depth=request.depth,
        max_sources=request.max_sources,
        source_types=source_types,
    )
    pipeline = DeepResearchPipeline(config=config)

    try:
        result = await pipeline.run(request.query)
        _results[run_id] = result
        _subchats[run_id] = SubchatEngine(result.report)
        _runs[run_id]["status"] = "completed"

        report = result.report
        sources = [
            {
                "title": s.title,
                "url": s.url,
                "source_type": s.source_type,
                "relevance_score": round(s.relevance_score, 3),
                "snippet": s.snippet[:300] if s.snippet else "",
                "domain": s.domain,
            }
            for s in result.sources[:50]
        ]
        findings = [
            {
                "id": f.id,
                "headline": f.headline,
                "detail": f.detail,
                "confidence": f.confidence,
                "supporting_sources": f.supporting_sources,
                "related_concepts": f.related_concepts,
                "subchat_seed": f.subchat_seed,
            }
            for f in report.key_findings
        ]

        return QueryResponse(
            run_id=run_id,
            status="completed",
            answer=report.executive_summary,
            sources=sources,
            findings=findings,
            knowledge_graph=result.knowledge_graph.to_dict()
            if hasattr(result.knowledge_graph, "to_dict")
            else {
                "nodes": [
                    {"id": n.id, "label": n.label, "type": n.node_type}
                    for n in result.knowledge_graph.nodes
                ],
                "edges": [
                    {
                        "source": e.source_id,
                        "target": e.target_id,
                        "relation": e.relation,
                    }
                    for e in result.knowledge_graph.edges
                ],
            },
            stats={
                "sources_discovered": len(result.sources),
                "evidence_items": len(result.evidence),
                "verified_claims": len(result.verification.verified),
                "likely_claims": len(result.verification.likely),
                "findings_count": len(report.key_findings),
                "graph_nodes": len(result.knowledge_graph.nodes),
                "graph_edges": len(result.knowledge_graph.edges),
            },
        )

    except Exception as exc:
        _runs[run_id]["status"] = "error"
        return QueryResponse(
            run_id=run_id, status="error", error=str(exc)
        )


# ---------------------------------------------------------------------------
# GET /query/stream — SSE streaming research
# ---------------------------------------------------------------------------

@app.get("/query/stream")
async def stream_query(
    q: str = Query(..., min_length=5),
    depth: str = Query("standard"),
    research_mode: bool = Query(True),
) -> StreamingResponse:
    source_types = (
        ["wikipedia", "arxiv", "semanticscholar"]
        if research_mode
        else ["wikipedia"]
    )
    config = PipelineConfig(depth=depth, source_types=source_types)
    pipeline = DeepResearchPipeline(config=config)

    async def _generate() -> AsyncIterator[str]:
        run_id = str(uuid.uuid4())
        yield f"data: {json.dumps({'type': 'start', 'run_id': run_id})}\n\n"

        try:
            async for event in pipeline.run_streaming(q):
                yield f"data: {json.dumps({'type': 'event', 'stage': event.stage, 'status': event.status, 'message': event.message, 'data': event.data})}\n\n"

            # After streaming completes, send final result
            result = await pipeline.run(q)
            _results[run_id] = result
            _subchats[run_id] = SubchatEngine(result.report)

            report = result.report
            final_payload = {
                "type": "result",
                "run_id": run_id,
                "answer": report.executive_summary,
                "title": report.title,
                "sources": [
                    {
                        "title": s.title,
                        "url": s.url,
                        "source_type": s.source_type,
                        "relevance_score": round(s.relevance_score, 3),
                        "snippet": s.snippet[:300] if s.snippet else "",
                    }
                    for s in result.sources[:30]
                ],
                "findings": [
                    {
                        "id": f.id,
                        "headline": f.headline,
                        "detail": f.detail,
                        "confidence": f.confidence,
                    }
                    for f in report.key_findings
                ],
                "stats": {
                    "sources_discovered": len(result.sources),
                    "evidence_items": len(result.evidence),
                    "verified_claims": len(result.verification.verified),
                    "findings_count": len(report.key_findings),
                },
            }
            yield f"data: {json.dumps(final_payload)}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /sources — sources for a completed run
# ---------------------------------------------------------------------------

@app.get("/sources")
async def get_sources(run_id: str = Query(...)) -> dict[str, Any]:
    result = _results.get(run_id)
    if not result:
        raise HTTPException(404, "Run not found or not completed.")
    return {
        "run_id": run_id,
        "sources": [
            {
                "title": s.title,
                "url": s.url,
                "source_type": s.source_type,
                "relevance_score": round(s.relevance_score, 3),
                "snippet": s.snippet[:500] if s.snippet else "",
                "domain": s.domain,
                "is_open_access": s.is_open_access,
            }
            for s in result.sources
        ],
    }


# ---------------------------------------------------------------------------
# GET /status — engine status
# ---------------------------------------------------------------------------

@app.get("/status")
async def get_status() -> dict[str, Any]:
    return {
        "engine": "nex-research-engine",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "active_runs": sum(
            1 for r in _runs.values() if r["status"] == "running"
        ),
        "completed_runs": sum(
            1 for r in _runs.values() if r["status"] == "completed"
        ),
        "corpus": {
            "books_indexed": 0,
            "chunks_generated": 0,
            "vector_indexes_loaded": 0,
            "packs_processed": 0,
            "note": "Local corpus integration pending — currently using web sources.",
        },
        "capabilities": {
            "wikipedia": True,
            "arxiv": True,
            "semantic_scholar": True,
            "zayvora": bool(os.environ.get("ZAYVORA_ENDPOINT")),
            "local_corpus": False,
        },
    }


# ---------------------------------------------------------------------------
# POST /subchat — follow-up questions on a finding
# ---------------------------------------------------------------------------

@app.post("/subchat")
async def subchat(request: SubchatRequest) -> StreamingResponse:
    engine = _subchats.get(request.run_id)
    if not engine:
        raise HTTPException(404, "Run not found or not completed.")

    # Create thread if needed
    thread = engine.create_thread(request.finding_id)

    async def _generate() -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()

        def _sync_stream() -> list[str]:
            return list(engine.chat_stream(thread.thread_id, request.message))

        chunks = await loop.run_in_executor(None, _sync_stream)
        for chunk in chunks:
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
