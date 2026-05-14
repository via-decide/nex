#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, ORIG, DER, PRESS, PRIM = [ROOT / d for d in ("first_principles_raw", "first_principles_text", "constraint_origins", "architecture_derivations", "continuity_pressure_maps", "engineering_primitives")]
for p in (RAW, TXT, ORIG, DER, PRESS, PRIM): p.mkdir(parents=True, exist_ok=True)

docs = [
 {"title":"Kernel scheduling origins","text":"interrupt latency, process fairness, memory paging, synchronization primitives, device driver contention."},
 {"title":"Compute hierarchy constraints","text":"cache hierarchy, NUMA bandwidth, SIMD throughput, thermal throttling, voltage stability."},
 {"title":"Distributed continuity foundations","text":"graph theory, information theory, eventual consistency, vector clocks, replay divergence, reconciliation."},
]
manifest=[]
for i,d in enumerate(docs,1):
    sid=f"fp_{i:04d}"; (RAW/f"{sid}.json").write_text(json.dumps(d,indent=2)); (TXT/f"{sid}.txt").write_text(d["text"])
    origins=["memory_ceiling","latency_floor","thermal_limit","sync_pressure"]
    deriv=["constraint_detected","primitive_selected","architecture_formed","continuity_validated"]
    pressure=["memory_pressure","throughput_pressure","continuity_pressure","replay_pressure"]
    primitive=["scheduler","cache","virtual_memory","vector_clock_reconciliation"]
    (ORIG/f"{sid}.json").write_text(json.dumps({"id":sid,"origins":origins},indent=2)); (DER/f"{sid}.json").write_text(json.dumps({"id":sid,"derivations":deriv},indent=2)); (PRESS/f"{sid}.json").write_text(json.dumps({"id":sid,"pressures":pressure},indent=2)); (PRIM/f"{sid}.json").write_text(json.dumps({"id":sid,"primitives":primitive},indent=2))
    manifest.append({"id":sid,"title":d["title"],"text":str(TXT/f"{sid}.txt"),"origins":origins,"pressures":pressure,"primitives":primitive})

(ROOT/"metadata").mkdir(exist_ok=True)
(ROOT/"metadata"/"first_principles_manifest.json").write_text(json.dumps(manifest,indent=2))
print(f"Harvested {len(manifest)} first-principles artifacts")
