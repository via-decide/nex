"""
Module 7 — Zayvora Integration

Bridges research findings with Zayvora's computational simulation and
technical analysis tools. When a research finding requires quantitative
validation, this module dispatches the appropriate Zayvora tool,
collects results, and returns structured output for inclusion in the report.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import httpx


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
# Mock / local execution (used when Zayvora endpoint is unavailable)
# ---------------------------------------------------------------------------

def _mock_traffic_simulation(params: dict[str, Any]) -> dict[str, Any]:
    """Deterministic mock for traffic simulation."""
    vehicles = params.get("vehicle_count", 1000)
    rsu_spacing = params.get("rsu_spacing_m", 500)
    v2x_penetration = params.get("v2x_penetration_pct", 30)

    # Simple analytical approximation
    base_congestion = max(0, 1 - vehicles / 5000)
    v2x_benefit = v2x_penetration / 100 * 0.25
    congestion_reduction = base_congestion + v2x_benefit
    avg_latency_ms = max(5, 50 - (1000 / rsu_spacing) * 2)

    return {
        "congestion_reduction_pct": round(congestion_reduction * 100, 1),
        "avg_communication_latency_ms": round(avg_latency_ms, 1),
        "rsu_coverage_pct": min(100, round(1000 / rsu_spacing * 10, 1)),
        "simulation_type": "analytical_approximation",
        "parameters_used": params,
    }


def _mock_sensor_network(params: dict[str, Any]) -> dict[str, Any]:
    area_km2 = params.get("area_km2", 10)
    rsu_count = params.get("rsu_count", 20)
    freq_ghz = params.get("frequency_ghz", 5.9)

    coverage_per_rsu = (5.9 / freq_ghz) * 0.3  # km²
    total_coverage = min(area_km2, rsu_count * coverage_per_rsu)
    coverage_pct = (total_coverage / area_km2) * 100

    return {
        "coverage_pct": round(coverage_pct, 1),
        "avg_rssi_dbm": -65 + (rsu_count / area_km2) * 5,
        "handoff_rate_per_km": round(rsu_count / (area_km2 ** 0.5), 2),
        "simulation_type": "analytical_approximation",
        "parameters_used": params,
    }


def _mock_data_analysis(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "analysis_type": params.get("analysis_type", "descriptive"),
        "note": "Mock analysis — connect Zayvora endpoint for real computation.",
        "parameters_used": params,
    }


_MOCK_HANDLERS: dict[ZayvoraToolType, Any] = {
    ZayvoraToolType.TRAFFIC_SIMULATION: _mock_traffic_simulation,
    ZayvoraToolType.SENSOR_NETWORK_MODEL: _mock_sensor_network,
    ZayvoraToolType.DATA_ANALYSIS: _mock_data_analysis,
}


# ---------------------------------------------------------------------------
# Zayvora Integration
# ---------------------------------------------------------------------------

class ZayvoraIntegration:
    """
    Dispatch research requests to Zayvora computational tools.

    If ZAYVORA_ENDPOINT is not set, falls back to analytical mock outputs.

    Usage:
        zayvora = ZayvoraIntegration()
        result = await zayvora.run(request)
    """

    def __init__(self) -> None:
        self._endpoint = os.environ.get("ZAYVORA_ENDPOINT", "")
        self._api_key = os.environ.get("ZAYVORA_API_KEY", "")
        self._use_mock = not self._endpoint

    async def run(self, request: ZayvoraRequest) -> ZayvoraResult:
        """Execute a Zayvora tool and return structured results."""
        if self._use_mock:
            return await self._run_mock(request)
        return await self._run_remote(request)

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

    async def _run_mock(self, request: ZayvoraRequest) -> ZayvoraResult:
        handler = _MOCK_HANDLERS.get(request.tool_type)
        if handler:
            output = handler(request.parameters)
            summary = (
                f"Mock {request.tool_type.value} simulation completed. "
                f"Key result: {list(output.items())[0][0]}={list(output.values())[0]}. "
                f"Connect a Zayvora endpoint for production-quality results."
            )
        else:
            output = {"note": "No mock handler for this tool type."}
            summary = "Tool executed in mock mode with no specific output handler."

        return ZayvoraResult(
            request=request,
            status="success",
            output=output,
            summary=summary,
        )

    async def _run_remote(self, request: ZayvoraRequest) -> ZayvoraResult:
        """Execute Zayvora tool on remote endpoint.

        Args:
            request: Structured Zayvora invocation request.

        Returns:
            A successful or error ``ZayvoraResult`` if endpoint processing fails.

        Raises:
            None.
        """
        payload = {
            "tool": request.tool_type.value,
            "parameters": request.parameters,
            "context": request.context,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._endpoint}/run",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            return ZayvoraResult(
                request=request,
                status=data.get("status", "success"),
                output=data.get("output", {}),
                summary=data.get("summary", ""),
                artifacts=data.get("artifacts", []),
            )
        except httpx.HTTPError as exc:
            error_msg = f"Zayvora HTTP error: {exc}"
            print(f"[ZayvoraIntegration._run_remote] {error_msg}")
            return ZayvoraResult(
                request=request,
                status="error",
                output={},
                summary="Zayvora tool execution failed due to network error.",
                error=error_msg,
            )
        except Exception as exc:
            error_msg = f"Zayvora execution error: {exc}"
            print(f"[ZayvoraIntegration._run_remote] {error_msg}")
            return ZayvoraResult(
                request=request,
                status="error",
                output={},
                summary="Zayvora tool execution failed.",
                error=error_msg,
            )
