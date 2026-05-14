#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "industrial_manifest.json"
OUT = ROOT / "industrial_lineage"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []

rows = []
for item in sorted(items, key=lambda x: x["id"]):
    rows.append({
      "facility_type": "factory_automation_cell" if "robotics" in item["title"].lower() else "process_control_facility",
      "industrial_constraints": ["deterministic cycle time", "bounded actuator response"],
      "timing_constraints": ["control loop jitter < 5ms", "failover ack < 200ms"],
      "safety_dependencies": ["IEC 61508", "SIL controls"],
      "electrical_constraints": ["voltage stability", "overload protection"],
      "embedded_dependencies": ["PLC runtime", "RTOS task scheduling"],
      "operator_authority": ["manual_override", "restart_approval"],
      "failure_modes": ["sensor_noise", "timing_failure", "actuator_divergence"],
      "recovery_sequences": ["safe_shutdown", "diagnostics", "controlled_restart"],
      "continuity_lineage": item.get("lineage", []),
    })

(OUT / "industrial_replay_manifests.json").write_text(json.dumps(rows, indent=2))
print(f"Generated {len(rows)} industrial manifests")
