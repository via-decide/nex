#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "ai_runtime_manifest.json"
OUT = ROOT / "runtime_continuity_maps"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []
maps=[]
for x in sorted(items,key=lambda y:y["id"]):
    seq=["quantization_change","embedding_variance","token_probability_shift","reasoning_divergence","replay_mismatch","continuity_admissibility_check"]
    maps.append({"id":x["id"],"states":[{"state":s,"next":seq[i+1] if i+1<len(seq) else None,"edge_id":hashlib.sha1(f'{x["id"]}|{s}|{i}'.encode()).hexdigest()[:12]} for i,s in enumerate(seq)]})
(OUT/"runtime_continuity_maps.json").write_text(json.dumps(maps,indent=2))
print(f"Built {len(maps)} runtime continuity maps")
