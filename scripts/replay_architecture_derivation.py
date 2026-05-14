#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "engineering_primitives" / "primitive_derivations.json"
OUT = ROOT / "architecture_derivations"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(INP.read_text()) if INP.exists() else []

CLASSES=["THERMAL_PRESSURE_DIVERGENCE","MEMORY_PRESSURE_DIVERGENCE","LATENCY_PRESSURE_DIVERGENCE","SYNCHRONIZATION_DIVERGENCE","CONTINUITY_COLLAPSE","AUTHORITY_COLLAPSE","REPLAY_DISCONTINUITY","UNKNOWN_ENGINEERING_STATE"]
replays=[]
for x in items:
    steps=[s["step"] for s in x.get("chain",[])]; label="UNKNOWN_ENGINEERING_STATE"
    if any("memory" in s or "cache" in s for s in steps): label="MEMORY_PRESSURE_DIVERGENCE"
    elif any("latency" in s for s in steps): label="LATENCY_PRESSURE_DIVERGENCE"
    elif any("replay" in s for s in steps): label="REPLAY_DISCONTINUITY"
    replays.append({"id":x["id"],"replay_targets":["kernel evolution","distributed emergence","orchestration formation","replay-system necessity","local-first sovereignty"],"causal_chain":steps,"divergence_class":label,"allowed_classes":CLASSES,"uncertainty":"lineage_missing" if not steps else "none"})
(OUT/"architecture_replay.json").write_text(json.dumps(replays,indent=2))
print(f"Replayed {len(replays)} architecture derivations")
