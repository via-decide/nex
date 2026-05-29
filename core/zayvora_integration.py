"""
Module 7 — Zayvora Integration

Bridges research findings with Zayvora's computational simulation and
technical analysis tools. When a research finding requires quantitative
validation, this module dispatches the appropriate Zayvora tool,
collects results, and returns structured output for inclusion in the report.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import ValidationError

from .sandbox import ExecutionSandbox
from schemas.zayvora_tools import ZayvoraToolInvocation


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class ZayvoraToolType(str, Enum):
    TRAFFIC_SIMULATION = "traffic_simulation"
    SENSOR_NETWORK_MODEL = "sensor_network_model"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    NUMERICAL_MODELING = "numerical_modeling"
    CUSTOM = "custom"


_TOOL_DESCRIPTIONS: dict[ZayvoraToolType, str] = {
    ZayvoraToolType.TRAFFIC_SIMULATION: (
        "Simulate traffic flow, congestion, and V2X communication effects "
        "on road networks using SUMO or custom simulator."
    ),
    ZayvoraToolType.SENSOR_NETWORK_MODEL: (
        "Model RSU/sensor placement, coverage, and communication latency "
        "across a given geographic area."
    ),
    ZayvoraToolType.CODE_GENERATION: (
        "Generate runnable code (Python, C++, MATLAB) to implement or test "
        "a described algorithm or protocol."
    ),
    ZayvoraToolType.DATA_ANALYSIS: (
        "Analyse datasets, compute statistics, generate visualisations, "
        "and return structured analysis results."
    ),
    ZayvoraToolType.NUMERICAL_MODELING: (
        "Run numerical models (finite-element, Monte Carlo, ODE solvers) "
        "for quantitative research validation."
    ),
    ZayvoraToolType.CUSTOM: "Custom Zayvora tool invocation.",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ZayvoraRequest:
    tool_type: ZayvoraToolType
    parameters: dict[str, Any]
    context: str                    # research finding or question that triggered this
    finding_id: str | None = None


@dataclass
class ZayvoraResult:
    request: ZayvoraRequest
    status: str                     # "success" | "error" | "queued"
    output: dict[str, Any]
    summary: str                    # human-readable 2-3 sentence summary
    artifacts: list[dict[str, str]] = field(default_factory=list)  # {"type": "image", "url": "..."}
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    error: str | None = None


# ---------------------------------------------------------------------------
# Zayvora Integration
# ---------------------------------------------------------------------------

class ZayvoraIntegration:
    """
    Dispatch research requests to Zayvora computational tools.

    All tool calls are validated and executed inside the local sandbox.

    Usage:
        zayvora = ZayvoraIntegration()
        result = await zayvora.run(request)
    """

    def __init__(self) -> None:
        self._sandbox = ExecutionSandbox()

    async def run(self, request: ZayvoraRequest) -> ZayvoraResult:
        """Execute a Zayvora tool inside an ephemeral sandbox."""
        return await self._run_sandbox(request)

    async def run_batch(self, requests: list[ZayvoraRequest]) -> list[ZayvoraResult]:
        """Run multiple Zayvora requests in parallel."""
        tasks = [asyncio.create_task(self.run(r)) for r in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = []
        for i, r in enumerate(results):
            if isinstance(r, ZayvoraResult):
                output.append(r)
            else:
                output.append(ZayvoraResult(
                    request=requests[i],
                    status="error",
                    output={},
                    summary="Zayvora tool execution failed.",
                    error=str(r),
                ))
        return output

    def build_request_from_finding(
        self,
        finding_headline: str,
        tool_type: ZayvoraToolType,
        parameters: dict[str, Any],
        finding_id: str | None = None,
    ) -> ZayvoraRequest:
        """Convenience builder for creating a ZayvoraRequest from a finding."""
        return ZayvoraRequest(
            tool_type=tool_type,
            parameters=parameters,
            context=finding_headline,
            finding_id=finding_id,
        )

    def available_tools(self) -> list[dict[str, str]]:
        """List all available Zayvora tools with descriptions."""
        return [
            {"type": t.value, "description": desc}
            for t, desc in _TOOL_DESCRIPTIONS.items()
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_sandbox(self, request: ZayvoraRequest) -> ZayvoraResult:
        try:
            parameters = dict(request.parameters)
            limits = parameters.pop("limits", parameters.pop("_limits", None))
            invocation = ZayvoraToolInvocation(
                tool_type=request.tool_type.value,
                parameters=parameters,
                context=request.context,
                finding_id=request.finding_id,
                **({"limits": limits} if isinstance(limits, dict) else {}),
            )
        except ValidationError as exc:
            return ZayvoraResult(
                request=request,
                status="error",
                output={},
                summary="Zayvora input contract validation failed.",
                error=f"ExecutionError: invalid sandbox payload: {exc}",
            )

        result = self._sandbox.execute(invocation)
        return ZayvoraResult(
            request=request,
            status=result.status,
            output={**result.output, "stdout": result.stdout, "stderr": result.stderr},
            summary=(
                f"Sandboxed {request.tool_type.value} execution completed."
                if result.status == "success"
                else "Sandboxed Zayvora execution failed gracefully."
            ),
            error=result.error,
        )
