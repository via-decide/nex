#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "first_principles_manifest.json"
OUT = ROOT / "constraint_pressure_maps"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []
rows=[]
for x in sorted(items,key=lambda y:y["id"]):
    rows.append({"id":x["id"],"thermal_pressure":"moderate","synchronization_pressure":"high","memory_pressure":"high","throughput_pressure":"high","continuity_pressure":"high","orchestration_pressure":"medium","replay_pressure":"high","authority_pressure":"medium","evolution_path":["larger_models","vram_exhaustion","quantization_systems","kv_cache_optimization","scheduler_complexity","replay_instability"]})
(OUT/"constraint_pressure_maps.json").write_text(json.dumps(rows,indent=2))
print(f"Built {len(rows)} constraint pressure maps")
