#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "physical_constraint_maps" / "physical_constraint_maps.json"
OUT = ROOT / "physical_divergence_maps"; OUT.mkdir(parents=True, exist_ok=True)
maps = json.loads(INP.read_text()) if INP.exists() else []
replays=[]
for x in maps:
    steps=[s["step"] for s in x.get("derivation",[])]; uncertainty="none" if steps else "UNKNOWN_PHYSICAL_STATE"
    replays.append({"id":x["id"],"replay_targets":["thermodynamic_pressure","synchronization_instability","signal_propagation","energy_bottlenecks","timing_collapse","memory_bandwidth_pressure"],"causal_order":steps,"lineage_supported":bool(steps),"uncertainty":uncertainty})
(OUT/"physical_reasoning_replay.json").write_text(json.dumps(replays,indent=2))
print(f"Replayed {len(replays)} physical reasoning chains")
