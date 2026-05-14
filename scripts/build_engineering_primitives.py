#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "first_principles_manifest.json"
OUT = ROOT / "engineering_primitives"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []

chains=[]
for x in sorted(items,key=lambda y:y["id"]):
    chain=["slow_memory_access","cache_hierarchy","locality_optimization","paging_systems","virtual_memory","scheduler_coordination"] if "Kernel" in x["title"] else ["distributed_latency","eventual_consistency","vector_clocks","reconciliation_systems","replay_divergence_handling"]
    chains.append({"id":x["id"],"chain":[{"step":s,"next":chain[i+1] if i+1<len(chain) else None,"edge_id":hashlib.sha1(f'{x["id"]}|{s}|{i}'.encode()).hexdigest()[:12]} for i,s in enumerate(chain)]})
(OUT/"primitive_derivations.json").write_text(json.dumps(chains,indent=2))
print(f"Built {len(chains)} primitive derivations")
