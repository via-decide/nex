#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "industrial_lineage" / "industrial_replay_manifests.json"
OUT = ROOT / "industrial_lineage"; OUT.mkdir(parents=True, exist_ok=True)
manifests = json.loads(INP.read_text()) if INP.exists() else []

rows = []
for i, m in enumerate(manifests, start=1):
    rows.append({
      "industrial_problem": f"facility_{i}_deterministic_recovery",
      "facility_constraints": m.get("industrial_constraints", []),
      "electrical_constraints": m.get("electrical_constraints", []),
      "embedded_constraints": m.get("embedded_dependencies", []),
      "mathematics_required": ["control stability", "queueing bounds", "timing analysis"],
      "control_systems": ["PLC", "SCADA", "DCS"],
      "safety_requirements": m.get("safety_dependencies", []),
      "failure_modes": m.get("failure_modes", []),
      "continuity_requirements": m.get("continuity_lineage", []),
      "operator_dependencies": m.get("operator_authority", []),
    })

(OUT / "industrial_sovereignty_dataset.json").write_text(json.dumps(rows, indent=2))
print(f"Wrote {len(rows)} industrial sovereignty records")
