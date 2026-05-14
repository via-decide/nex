#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "replay_manifests" / "replay_manifests.json"
OUT = ROOT / "constraint_matrix"; OUT.mkdir(parents=True, exist_ok=True)
manifests = json.loads(INP.read_text()) if INP.exists() else []

rows = []
for m in manifests:
    maths = sorted(set(m.get("mathematical_dependencies", []) or ["unknown_math"]))
    for math_dep in maths:
        rows.append({"math": math_dep, "electrical": sorted(set(m.get("electrical_dependencies", []))), "electronics": sorted(set(m.get("electronics_dependencies", []))), "embedded": sorted(set(m.get("engineering_constraints", []))), "distributed": sorted(set([c for c in m.get("continuity_lineage", []) if "continuity" in c.lower() or "orchestration" in c.lower()])), "example_links": ["fourier transform <-> dsp <-> rf systems", "thermal constraint <-> power regulation <-> signal integrity"]})

(OUT / "cross_domain_constraint_matrix.json").write_text(json.dumps(rows, indent=2))
print(f"Wrote {len(rows)} constraint rows")
