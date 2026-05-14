#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "ai_runtime_manifest.json"
OUT = ROOT / "inference_lineage"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []
rows=[]
for x in sorted(items,key=lambda y:y["id"]):
    rows.append({"model_family":"llama-family" if "llama" in x["title"].lower() else "mixed-runtime-stack","runtime_constraints":["runtime replaceability","provider compatibility"],"memory_constraints":x.get("memory",[]),"quantization_profile":["q4","q5","q8","mixed_precision"],"scheduler_dependencies":["batch scheduler","prefill-decode separation"],"replay_boundaries":["token stream boundary","runtime swap boundary"],"continuity_guarantees":["deterministic replay window","canonical checksum"],"divergence_classes":["QUANTIZATION_DIVERGENCE","SCHEDULER_DIVERGENCE","HARDWARE_DRIFT"],"canonical_lineage":x.get("lineage",[])})
(OUT/"ai_runtime_manifests.json").write_text(json.dumps(rows,indent=2))
print(f"Generated {len(rows)} ai runtime manifests")
