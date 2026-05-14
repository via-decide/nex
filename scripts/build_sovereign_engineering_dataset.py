#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, OUT = ROOT / "metadata", ROOT / "engineering_graph"
OUT.mkdir(exist_ok=True)
rows = []
for f in META.glob("*.semantic.json"):
    s = json.loads(f.read_text())
    rows.append({
        "problem": f"Synthesize constraints from {Path(s['source']).name}",
        "physical_constraints": s.get("engineering_constraints", []),
        "electrical_constraints": s.get("electrical_concepts", []),
        "electronics_constraints": s.get("electronics_concepts", []),
        "mathematics_required": s.get("math_domains", []),
        "failure_modes": s.get("failure_modes", []),
        "embedded_considerations": s.get("systems_thinking", []),
        "real_world_tradeoffs": ["safety vs performance", "efficiency vs cost"],
        "continuity_relevance": s.get("systems_thinking", []),
    })
(OUT / "sovereign_engineering_dataset.json").write_text(json.dumps(rows, indent=2))
print(f"Wrote {len(rows)} dataset nodes")
