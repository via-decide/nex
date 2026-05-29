"""Strict Pydantic contracts for sandboxed Zayvora tool execution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ToolName = Literal[
    "traffic_simulation",
    "sensor_network_model",
    "code_generation",
    "data_analysis",
    "numerical_modeling",
    "custom",
]


class SandboxLimits(BaseModel):
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    memory_mb: int = Field(default=256, ge=32, le=2048)


class TrafficSimulationInput(BaseModel):
    vehicle_count: int = Field(default=1000, ge=0, le=1_000_000)
    rsu_spacing_m: float = Field(default=500, gt=0, le=100_000)
    v2x_penetration_pct: float = Field(default=30, ge=0, le=100)


class SensorNetworkInput(BaseModel):
    area_km2: float = Field(default=10, gt=0, le=1_000_000)
    rsu_count: int = Field(default=20, ge=0, le=1_000_000)
    frequency_ghz: float = Field(default=5.9, gt=0, le=300)


class ScriptToolInput(BaseModel):
    script: str = Field(default="", max_length=20_000)
    inputs: dict[str, Any] = Field(default_factory=dict)


class ZayvoraToolInvocation(BaseModel):
    tool_type: ToolName
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: str = ""
    finding_id: str | None = None
    limits: SandboxLimits = Field(default_factory=SandboxLimits)

    def typed_parameters(self) -> BaseModel:
        if self.tool_type == "traffic_simulation":
            return TrafficSimulationInput(**self.parameters)
        if self.tool_type == "sensor_network_model":
            return SensorNetworkInput(**self.parameters)
        if self.tool_type in {"code_generation", "data_analysis", "numerical_modeling", "custom"}:
            return ScriptToolInput(**self.parameters)
        return ScriptToolInput(inputs=self.parameters)
