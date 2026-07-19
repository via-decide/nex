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
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Core pipeline
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pipeline import DeepResearchPipeline, PipelineConfig, PipelineResult
from core.subchat_engine import SubchatEngine, SubchatMessage
from core.database import NexDatabase
from core.auth import Principal, Role, authenticate, authorize_object
from core.security import SecurityMiddleware, reject_executable_payload
from core.tool_registry import REGISTRY, execute_tool


# ---------------------------------------------------------------------------
# Embedded SQLite persistence
# ---------------------------------------------------------------------------

_db = NexDatabase()


def _as_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _as_obj(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_obj(v) for v in value]
    return value


def _report_obj(report: dict[str, Any]) -> Any:
    obj = _as_obj(report)
    obj.key_findings = [_as_obj(f) for f in report.get("key_findings", [])]
    return obj


def _markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report.get('title', 'Research Report')}", "", "## Executive Summary", report.get("executive_summary", "")]
    lines.extend(["", "## Key Findings"])
    for finding in report.get("key_findings", []):
        lines.append(f"- **{finding.get('confidence', '')}** {finding.get('headline', '')}")
    return "\n".join(lines)


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
    allow_origins=[o.strip() for o in os.getenv("NEX_ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityMiddleware)


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
        _db.update_run(run_id, status="running")
        result: PipelineResult = await pipeline.run(request.question)
        _db.save_result(run_id, result)
    except Exception as exc:
        _db.update_run(run_id, status="error", error=str(exc), completed_at=datetime.utcnow().isoformat() + "Z")


@app.post("/api/research/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(authenticate),
) -> ResearchStartResponse:
    reject_executable_payload(request.model_dump())
    run_id = str(uuid.uuid4())
    _db.create_run(run_id, request.question, request.depth)
    background_tasks.add_task(_run_pipeline, run_id, request)
    return ResearchStartResponse(
        run_id=run_id,
        status="queued",
        message="Research pipeline started. Poll /api/research/{run_id} for status.",
    )


@app.get("/api/research/{run_id}")
async def get_research_run(run_id: str, principal: Principal = Depends(authenticate)) -> dict[str, Any]:
    authorize_object(principal, "research_runs", run_id, Role.READER)
    run = _db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    return dict(run)


@app.get("/api/research/{run_id}/report/markdown")
async def get_report_markdown(run_id: str, principal: Principal = Depends(authenticate)) -> dict[str, str]:
    authorize_object(principal, "reports", run_id, Role.READER)
    report = _db.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or pipeline not completed.")
    return {"markdown": _markdown(report)}


@app.get("/api/research/{run_id}/report/json")
async def get_report_json(run_id: str, principal: Principal = Depends(authenticate)) -> dict[str, Any]:
    authorize_object(principal, "reports", run_id, Role.READER)
    report = _db.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or pipeline not completed.")
    return report


@app.get("/api/research/{run_id}/stream")
async def stream_research(run_id: str, principal: Principal = Depends(authenticate)) -> StreamingResponse:
    authorize_object(principal, "research_runs", run_id, Role.READER)
    """
    SSE stream of pipeline events for a run.
    Clients connect and receive Server-Sent Events as stages complete.
    """
    run = _db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def _event_generator() -> AsyncIterator[str]:
        sent = 0
        while True:
            events = (_db.get_run(run_id) or {}).get("events", [])
            while sent < len(events):
                event = events[sent]
                yield f"data: {json.dumps(event)}\n\n"
                sent += 1
            status = (_db.get_run(run_id) or {}).get("status", "queued")
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
async def create_subchat(request: SubchatCreateRequest, principal: Principal = Depends(authenticate)) -> dict[str, Any]:
    authorize_object(principal, "research_runs", request.run_id, Role.READER)
    """Create a subchat thread for a specific finding.

    Args:
        request: Subchat creation payload.

    Returns:
        Serialized thread record.

    Raises:
        HTTPException: If run does not exist or finding_id is invalid.
    """
    report = _db.get_report(request.run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Research run not found or not completed.")
    engine = SubchatEngine(_report_obj(report))
    try:
        thread = engine.create_thread(request.finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    exported = engine.export_thread(thread.thread_id)
    _db.save_thread(exported, request.run_id, request.finding_id)
    return exported


@app.post("/api/subchat/{thread_id}/message")
async def subchat_message(
    thread_id: str,
    request: SubchatMessageRequest,
) -> StreamingResponse:
    """Stream subchat response via SSE."""
    stored_thread = _db.get_thread(thread_id)
    if not stored_thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    report = _db.get_report(stored_thread.get("run_id", ""))
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found.")
    engine = SubchatEngine(_report_obj(report))
    thread = engine.create_thread(stored_thread["finding_id"])
    thread.thread_id = thread_id
    thread.messages = [SubchatMessage(role=m["role"], content=m["content"], timestamp=m.get("timestamp", "")) for m in stored_thread.get("messages", [])]
    engine._threads[thread_id] = thread

    async def _generate() -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()

        def _sync_stream() -> list[str]:
            chunks = list(engine.chat_stream(thread_id, request.message))
            _db.save_thread(engine.export_thread(thread_id), stored_thread.get("run_id", ""), stored_thread["finding_id"])
            return chunks

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
async def export_subchat(thread_id: str, principal: Principal = Depends(authenticate)) -> dict[str, Any]:
    authorize_object(principal, "subchat_threads", thread_id, Role.READER)
    thread = _db.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    return thread


# ---------------------------------------------------------------------------
# Zayvora/tool endpoints
# ---------------------------------------------------------------------------

@app.post("/api/zayvora/run")
async def run_zayvora(request: ZayvoraRunRequest, principal: Principal = Depends(authenticate)) -> dict[str, Any]:
    """Execute only registered, non-code tools; caller-supplied source is rejected."""
    try:
        output = execute_tool(request.tool_type, request.parameters, principal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", "tool_id": request.tool_type, "output": output, "summary": "Allowlisted tool execution completed."}


@app.get("/api/zayvora/tools")
async def list_zayvora_tools() -> list[dict[str, Any]]:
    return [{k: v for k, v in spec.__dict__.items() if k != "handler"} for spec in REGISTRY.values()]
