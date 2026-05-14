#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "replay_manifests" / "replay_manifests.json"
OUT = ROOT / "replay_manifests"; OUT.mkdir(parents=True, exist_ok=True)
manifests = json.loads(INP.read_text()) if INP.exists() else []

RULES = [("thermal", "THERMAL_DIVERGENCE"), ("signal", "SIGNAL_DIVERGENCE"), ("orchestration", "ORCHESTRATION_DIVERGENCE"), ("stability", "MATHEMATICAL_DIVERGENCE"), ("topology", "STRUCTURAL_DIVERGENCE")]

def classify(manifest):
    corpus = " ".join(manifest.get("failure_modes", []) + manifest.get("engineering_constraints", []) + manifest.get("continuity_lineage", [])).lower()
    for key, cls in RULES:
        if key in corpus: return cls
    return "UNKNOWN_CONTINUITY_STATE"

replays = []
for m in manifests:
    replays.append({"manifest_id": m["manifest_id"], "replay_summary": {"architecture_choices": sorted(set(m.get("electrical_dependencies", []) + m.get("electronics_dependencies", []))), "protocol_selections": [x for x in sorted(set(m.get("electronics_dependencies", []))) if x in {"spi", "i2c", "uart", "can", "ethernet"}], "topology_decisions": sorted(set(m.get("continuity_lineage", []))), "power_tradeoffs": m.get("design_tradeoffs", []), "embedded_constraints": sorted(set(m.get("engineering_constraints", []))), "numerical_approximations": sorted(set(m.get("mathematical_dependencies", []))), "orchestration_logic": sorted(set([x for x in m.get("continuity_lineage", []) if "orchestration" in x.lower()] or ["lineage-bound replay only"]))}, "divergence_classification": classify(m), "determinism_note": "Reconstruction is lineage-supported only; no inferred states beyond manifest evidence."})

(OUT / "engineering_reasoning_replay.json").write_text(json.dumps(replays, indent=2))
print(f"Replayed {len(replays)} manifests")
