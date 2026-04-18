"""
Nex Deep Research Engine — FastAPI Application

Endpoints:
  POST /api/research/start        — start a research pipeline run
  GET  /api/research/{run_id}     — get run status / results
  GET  /api/research/{run_id}/stream — SSE stream of pipeline events
  POST /api/subchat/create        — create a subchat thread for a finding
  POST /api/subchat/{thread_id}/message — send a message to a thread
  GET  /api/subchat/{thread_id}/export  — export a thread
  POST /api/zayvora/run           — run a Zayvora simulation
  GET  /api/health                — health check
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Core pipeline
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pipeline import DeepResearchPipeline, PipelineConfig, PipelineResult
from core.research_synthesizer import ResearchReport
from core.subchat_engine import SubchatEngine
from core.zayvora_integration import ZayvoraIntegration, ZayvoraRequest, ZayvoraToolType


# ---------------------------------------------------------------------------
# In-memory store (replace with PostgreSQL/Redis in production)
# ---------------------------------------------------------------------------

_runs: dict[str, dict[str, Any]] = {}
_reports: dict[str, ResearchReport] = {}
_subchats: dict[str, SubchatEngine] = {}  # keyed by run_id
_thread_to_engine: dict[str, str] = {}    # Maps thread_id -> run_id for fast lookup

_CLEANUP_CONFIG = {
    "max_age_seconds": 86400 * 7,  # 7 days
    "check_interval_seconds": 3600,  # 1 hour
}
_last_cleanup: float = time.time()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ResearchStartRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=1000)
    depth: str = Field("standard", pattern="^(standard|deep|exhaustive)$")
    max_sources: int = Field(30, ge=10, le=100)
    enable_zayvora: bool = False
    source_types: list[str] = Field(
        default=["wikipedia", "arxiv", "semanticscholar"]
    )


class ResearchStartResponse(BaseModel):
    run_id: str
    status: str
    message: str


class SubchatCreateRequest(BaseModel):
    run_id: str
    finding_id: str


class SubchatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ZayvoraRunRequest(BaseModel):
    tool_type: str
    parameters: dict[str, Any]
    context: str
    finding_id: str | None = None




async def _cleanup_old_runs() -> None:
    """Periodically clean up old completed runs.

    Prevents indefinite memory growth in in-memory stores.

    Returns:
        None.

    Raises:
        None.
    """
    global _last_cleanup
    now = time.time()

    # Only run cleanup every check_interval_seconds
    if now - _last_cleanup < _CLEANUP_CONFIG["check_interval_seconds"]:
        return

    _last_cleanup = now
    max_age = _CLEANUP_CONFIG["max_age_seconds"]
    cutoff_time = datetime.utcnow().timestamp() - max_age

    # Find old runs
    old_run_ids: list[str] = []
    for run_id, run in _runs.items():
        created_str = run.get("created_at", "")
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                created_ts = created_dt.timestamp()
                if created_ts < cutoff_time:
                    old_run_ids.append(run_id)
            except ValueError:
                pass

    # Clean up old runs
    for run_id in old_run_ids:
        _runs.pop(run_id, None)
        _reports.pop(run_id, None)
        _subchats.pop(run_id, None)
        print(f"[api._cleanup_old_runs] Removed old run {run_id}")

    if old_run_ids:
        print(f"[api._cleanup_old_runs] Removed {len(old_run_ids)} old runs")

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Nex Deep Research Engine starting up...")
    yield
    print("Nex Deep Research Engine shutting down.")


app = FastAPI(
    title="Nex Deep Research Engine",
    description="Autonomous multi-source research pipeline with evidence verification.",
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
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "nex-deep-research-engine",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Research pipeline endpoints
# ---------------------------------------------------------------------------

async def _run_pipeline(run_id: str, request: ResearchStartRequest) -> None:
    """Background task: execute the full research pipeline."""
    config = PipelineConfig(
        depth=request.depth,
        max_sources=request.max_sources,
        enable_zayvora=request.enable_zayvora,
        source_types=request.source_types,
    )
    pipeline = DeepResearchPipeline(config=config)
    try:
        _runs[run_id]["status"] = "running"
        result: PipelineResult = await pipeline.run(request.question)
        _reports[run_id] = result.report
        _subchats[run_id] = SubchatEngine(result.report)
        _runs[run_id].update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "events": [
                {"stage": e.stage, "status": e.status, "message": e.message, "data": e.data}
                for e in result.events
            ],
            "stats": {
                "sources_discovered": len(result.sources),
                "evidence_items": len(result.evidence),
                "verified_claims": len(result.verification.verified),
                "likely_claims": len(result.verification.likely),
                "findings": len(result.report.key_findings),
                "graph_nodes": len(result.knowledge_graph.nodes),
            },
        })
    except Exception as exc:
        _runs[run_id].update({
            "status": "error",
            "error": str(exc),
            "completed_at": datetime.utcnow().isoformat() + "Z",
        })


@app.post("/api/research/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    background_tasks: BackgroundTasks,
) -> ResearchStartResponse:
    # Run cleanup if needed
    await _cleanup_old_runs()

    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "run_id": run_id,
        "question": request.question,
        "status": "queued",
        "depth": request.depth,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "events": [],
    }
    background_tasks.add_task(_run_pipeline, run_id, request)
    return ResearchStartResponse(
        run_id=run_id,
        status="queued",
        message="Research pipeline started. Poll /api/research/{run_id} for status.",
    )


@app.get("/api/research/{run_id}")
async def get_research_run(run_id: str) -> dict[str, Any]:
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    response = dict(run)
    if run["status"] == "completed" and run_id in _reports:
        response["report"] = _reports[run_id].to_dict()
    return response


@app.get("/api/research/{run_id}/report/markdown")
async def get_report_markdown(run_id: str) -> dict[str, str]:
    report = _reports.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or pipeline not completed.")
    return {"markdown": report.to_markdown()}


@app.get("/api/research/{run_id}/report/json")
async def get_report_json(run_id: str) -> dict[str, Any]:
    report = _reports.get(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or pipeline not completed.")
    return report.to_dict()


@app.get("/api/research/{run_id}/stream")
async def stream_research(run_id: str) -> StreamingResponse:
    """
    SSE stream of pipeline events for a run.
    Clients connect and receive Server-Sent Events as stages complete.
    """
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def _event_generator() -> AsyncIterator[str]:
        sent = 0
        while True:
            events = _runs.get(run_id, {}).get("events", [])
            while sent < len(events):
                event = events[sent]
                yield f"data: {json.dumps(event)}\n\n"
                sent += 1
            status = _runs.get(run_id, {}).get("status", "queued")
            if status in ("completed", "error"):
                yield f"data: {json.dumps({'stage': 'done', 'status': status})}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Subchat endpoints
# ---------------------------------------------------------------------------

@app.post("/api/subchat/create")
async def create_subchat(request: SubchatCreateRequest) -> dict[str, Any]:
    """Create a subchat thread for a specific finding.

    Args:
        request: Subchat creation payload.

    Returns:
        Serialized thread record.

    Raises:
        HTTPException: If run does not exist or finding_id is invalid.
    """
    engine = _subchats.get(request.run_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Research run not found or not completed.")
    try:
        thread = engine.create_thread(request.finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Track thread-to-engine mapping for fast lookup
    _thread_to_engine[thread.thread_id] = request.run_id
    return engine.export_thread(thread.thread_id)


@app.post("/api/subchat/{thread_id}/message")
async def subchat_message(
    thread_id: str,
    request: SubchatMessageRequest,
) -> StreamingResponse:
    """Stream subchat response via SSE."""
    # Fast O(1) lookup using thread-to-engine map
    run_id = _thread_to_engine.get(thread_id)
    engine = _subchats.get(run_id) if run_id else None

    if not engine:
        raise HTTPException(status_code=404, detail="Thread not found.")

    async def _generate() -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()

        def _sync_stream() -> list[str]:
            return list(engine.chat_stream(thread_id, request.message))

        chunks = await loop.run_in_executor(None, _sync_stream)
        for chunk in chunks:
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/subchat/{thread_id}/export")
async def export_subchat(thread_id: str) -> dict[str, Any]:
    # Fast O(1) lookup using thread-to-engine map
    run_id = _thread_to_engine.get(thread_id)
    engine = _subchats.get(run_id) if run_id else None

    if not engine:
        raise HTTPException(status_code=404, detail="Thread not found.")

    thread = engine.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    return engine.export_thread(thread_id)


# ---------------------------------------------------------------------------
# Zayvora endpoints
# ---------------------------------------------------------------------------

@app.post("/api/zayvora/run")
async def run_zayvora(request: ZayvoraRunRequest) -> dict[str, Any]:
    zayvora = ZayvoraIntegration()
    try:
        tool_type = ZayvoraToolType(request.tool_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown tool type: {request.tool_type}")

    zreq = ZayvoraRequest(
        tool_type=tool_type,
        parameters=request.parameters,
        context=request.context,
        finding_id=request.finding_id,
    )
    result = await zayvora.run(zreq)
    return {
        "status": result.status,
        "output": result.output,
        "summary": result.summary,
        "artifacts": result.artifacts,
        "executed_at": result.executed_at,
    }


@app.get("/api/zayvora/tools")
async def list_zayvora_tools() -> list[dict[str, str]]:
    zayvora = ZayvoraIntegration()
    return zayvora.available_tools()
