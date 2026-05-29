"""Deterministic ephemeral sandbox for Zayvora calculations.

The sandbox launches a short-lived isolated Python process with a temporary
working directory, no shell, a minimal environment, and hard timeout/memory
bounds. The directory is deleted immediately after execution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any

from schemas.zayvora_tools import ZayvoraToolInvocation


@dataclass
class SandboxResult:
    status: str
    output: dict[str, Any]
    stdout: str
    stderr: str
    error: str | None = None


def _limit_resources(memory_mb: int) -> None:
    try:
        import resource
        memory = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except Exception:
        return


class ExecutionSandbox:
    """Run typed Zayvora tool payloads in disposable bounded processes."""

    def execute(self, invocation: ZayvoraToolInvocation) -> SandboxResult:
        script = invocation.typed_parameters()
        code = script.script if getattr(script, "script", "") else self._builtin_script(invocation.tool_type)
        payload = json.dumps(script.model_dump())
        with tempfile.TemporaryDirectory(prefix="nex-zayvora-") as workdir:
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", code],
                    input=payload,
                    text=True,
                    capture_output=True,
                    cwd=workdir,
                    env={"PYTHONHASHSEED": "0", "PATH": os.environ.get("PATH", "")},
                    timeout=invocation.limits.timeout_seconds,
                    preexec_fn=lambda: _limit_resources(invocation.limits.memory_mb) if os.name == "posix" else None,
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxResult("error", {}, exc.stdout or "", exc.stderr or "", f"ExecutionError: timeout after {invocation.limits.timeout_seconds}s")
        if proc.returncode != 0:
            return SandboxResult("error", {}, proc.stdout, proc.stderr, f"ExecutionError: process exited {proc.returncode}")
        try:
            return SandboxResult("success", json.loads(proc.stdout or "{}"), proc.stdout, proc.stderr)
        except json.JSONDecodeError as exc:
            return SandboxResult("error", {}, proc.stdout, proc.stderr, f"ExecutionError: invalid JSON output: {exc}")

    def _builtin_script(self, tool_type: str) -> str:
        if tool_type == "traffic_simulation":
            return """import json,sys\np=json.load(sys.stdin)\nv=p.get('vehicle_count',1000); s=p.get('rsu_spacing_m',500); pen=p.get('v2x_penetration_pct',30)\nbase=max(0,1-v/5000); benefit=pen/100*0.25; latency=max(5,50-(1000/s)*2)\nprint(json.dumps({'congestion_reduction_pct':round((base+benefit)*100,1),'avg_communication_latency_ms':round(latency,1),'rsu_coverage_pct':min(100,round(1000/s*10,1)),'simulation_type':'sandbox_analytical'}))\n"""
        if tool_type == "sensor_network_model":
            return """import json,sys,math\np=json.load(sys.stdin)\na=p.get('area_km2',10); r=p.get('rsu_count',20); f=p.get('frequency_ghz',5.9)\ncov=min(a,r*((5.9/f)*0.3)); print(json.dumps({'coverage_pct':round((cov/a)*100,1),'avg_rssi_dbm':-65+(r/a)*5,'handoff_rate_per_km':round(r/(a**0.5),2),'simulation_type':'sandbox_analytical'}))\n"""
        return """import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'status':'completed','inputs':p.get('inputs',{}),'note':'sandbox executed without external scientific dependencies'}))\n"""
