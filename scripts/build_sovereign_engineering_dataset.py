#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, OUT = ROOT / "metadata", ROOT / "engineering_graph"
OUT.mkdir(parents=True, exist_ok=True)

rows = []
for f in sorted(META.glob("*.semantic.json")):
    s = json.loads(f.read_text())
    rows.append({
      "problem": f"Engineer resilient design from {Path(s.get('source','unknown')).name}",
      "physical_constraints": sorted(set(s.get("engineering_constraints", []))),
      "electrical_constraints": sorted(set(s.get("electrical_concepts", []))),
      "electronics_constraints": sorted(set(s.get("electronics_concepts", []))),
      "mathematics_required": sorted(set(s.get("math_domains", []) + s.get("control_primitives", []))),
      "failure_modes": sorted(set(s.get("failure_modes", []))),
      "embedded_considerations": sorted(set(s.get("systems_thinking", []))),
      "real_world_tradeoffs": ["efficiency vs thermal headroom", "latency vs determinism", "cost vs reliability"],
      "continuity_relevance": [f"continuity::{v}" for v in sorted(set(s.get("systems_thinking", [])))],
    })

(OUT / "sovereign_engineering_dataset.json").write_text(json.dumps(rows, indent=2))
print(f"Wrote {len(rows)} dataset nodes")
