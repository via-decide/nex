#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "physical_manifest.json"
OUT = ROOT / "physical_constraint_maps"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []
maps=[]
for x in sorted(items,key=lambda y:y["id"]):
    seq=["increased_compute_density","thermal_pressure","clock_instability","synchronization_drift","replay_divergence","continuity_risk"] if "Physics" in x["title"] else ["memory_bandwidth_limit","inference_bottleneck","scheduler_pressure","token_latency_variance","orchestration_divergence"]
    maps.append({"id":x["id"],"derivation":[{"step":s,"next":seq[i+1] if i+1<len(seq) else None,"edge_id":hashlib.sha1(f'{x["id"]}|{s}|{i}'.encode()).hexdigest()[:12]} for i,s in enumerate(seq)]})
(OUT/"physical_constraint_maps.json").write_text(json.dumps(maps,indent=2))
print(f"Built {len(maps)} physical constraint maps")
