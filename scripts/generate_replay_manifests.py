#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, GRAPH = ROOT / "metadata", ROOT / "engineering_graph"
OUT = ROOT / "replay_manifests"; OUT.mkdir(parents=True, exist_ok=True)

def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default

dataset = load(GRAPH / "sovereign_engineering_dataset.json", [])
manifests = []
for i, row in enumerate(dataset, start=1):
    mid = hashlib.sha1(f"{row.get('problem','')}|{i}".encode()).hexdigest()[:16]
    manifests.append({
        "manifest_id": mid,
        "domain": "engineering_continuity",
        "source_artifacts": [row.get("problem", "unknown")],
        "engineering_constraints": row.get("physical_constraints", []),
        "mathematical_dependencies": row.get("mathematics_required", []),
        "electrical_dependencies": row.get("electrical_constraints", []),
        "electronics_dependencies": row.get("electronics_constraints", []),
        "failure_modes": row.get("failure_modes", []),
        "design_tradeoffs": row.get("real_world_tradeoffs", []),
        "continuity_lineage": row.get("continuity_relevance", []),
        "replay_primitives": ["lineage_trace", "constraint_recall", "failure_chain"],
    })

(OUT / "replay_manifests.json").write_text(json.dumps(manifests, indent=2))
print(f"Generated {len(manifests)} replay manifests")
