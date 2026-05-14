#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "inference_lineage" / "ai_runtime_manifests.json"
OUT = ROOT / "inference_lineage"; OUT.mkdir(parents=True, exist_ok=True)
man = json.loads(INP.read_text()) if INP.exists() else []
rows=[]
for i,m in enumerate(man,1):
    rows.append({"runtime_problem":f"runtime_continuity_case_{i}","hardware_constraints":["cpu/gpu memory bandwidth","numa locality"],"memory_constraints":m.get("memory_constraints",[]),"scheduler_constraints":m.get("scheduler_dependencies",[]),"quantization_dependencies":m.get("quantization_profile",[]),"failure_modes":["kv eviction","scheduler jitter","runtime incompatibility"],"divergence_risks":m.get("divergence_classes",[]),"continuity_requirements":m.get("canonical_lineage",[]),"replay_constraints":m.get("replay_boundaries",[])})
(OUT/"ai_sovereignty_dataset.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} ai sovereignty records")
