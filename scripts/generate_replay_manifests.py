#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, GRAPH = ROOT / "metadata", ROOT / "engineering_graph"
OUT = ROOT / "replay_manifests"; OUT.mkdir(parents=True, exist_ok=True)

def load(path, default): return json.loads(path.read_text()) if path.exists() else default

def from_semantic(s):
    name = Path(s.get("source", "unknown")).name
    return {
        "problem": f"Replay lineage for {name}", "physical_constraints": s.get("engineering_constraints", []),
        "electrical_constraints": s.get("electrical_concepts", []), "electronics_constraints": s.get("electronics_concepts", []),
        "mathematics_required": s.get("math_domains", []) + s.get("control_primitives", []), "failure_modes": s.get("failure_modes", []),
        "real_world_tradeoffs": ["stability vs responsiveness", "thermal margin vs performance"], "continuity_relevance": s.get("systems_thinking", []),
    }

dataset = load(GRAPH / "sovereign_engineering_dataset.json", [])
if not dataset: dataset = [from_semantic(json.loads(f.read_text())) for f in sorted(META.glob("*.semantic.json"))]
manifests = []
for i, row in enumerate(dataset, start=1):
    mid = hashlib.sha1(f"{row.get('problem','')}|{i}".encode()).hexdigest()[:16]
    manifests.append({"manifest_id": mid, "domain": "engineering_continuity", "source_artifacts": [row.get("problem", "unknown")], "engineering_constraints": sorted(set(row.get("physical_constraints", []))), "mathematical_dependencies": sorted(set(row.get("mathematics_required", []))), "electrical_dependencies": sorted(set(row.get("electrical_constraints", []))), "electronics_dependencies": sorted(set(row.get("electronics_constraints", []))), "failure_modes": sorted(set(row.get("failure_modes", []))), "design_tradeoffs": row.get("real_world_tradeoffs", []), "continuity_lineage": sorted(set(row.get("continuity_relevance", []))), "replay_primitives": ["lineage_trace", "constraint_recall", "failure_chain"]})

(OUT / "replay_manifests.json").write_text(json.dumps(manifests, indent=2))
print(f"Generated {len(manifests)} replay manifests")
