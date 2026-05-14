#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "physical_divergence_maps" / "physical_reasoning_replay.json"
OUT = ROOT / "physical_divergence_maps"; OUT.mkdir(parents=True, exist_ok=True)
rows=[]
for i,r in enumerate(json.loads(INP.read_text()) if INP.exists() else [],1):
    rows.append({"physical_problem":f"physical_continuity_case_{i}","mathematical_dependencies":["linear algebra","graph theory","information theory"],"energy_constraints":["finite power budget","heat dissipation limit"],"signal_constraints":["snr floor","clock jitter budget"],"timing_constraints":["latency bound","sync window"],"thermodynamic_pressures":["thermal density","hotspot accumulation"],"failure_modes":["signal corruption","timing drift","energy collapse"],"continuity_requirements":["causal order preservation","deterministic retry policy"],"replay_constraints":r.get("causal_order",[])})
(OUT/"physical_sovereignty_dataset.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} physical sovereignty rows")
