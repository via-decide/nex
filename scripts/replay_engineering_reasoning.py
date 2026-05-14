#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "replay_manifests" / "replay_manifests.json"
OUT = ROOT / "replay_manifests"; OUT.mkdir(parents=True, exist_ok=True)
manifests = json.loads(INP.read_text()) if INP.exists() else []

DIVERGENCE = {
    "thermal": "THERMAL_DIVERGENCE",
    "signal": "SIGNAL_DIVERGENCE",
    "orchestration": "ORCHESTRATION_DIVERGENCE",
    "stability": "MATHEMATICAL_DIVERGENCE",
}

def classify(manifest):
    corpus = " ".join(manifest.get("failure_modes", []) + manifest.get("engineering_constraints", [])).lower()
    for k, v in DIVERGENCE.items():
        if k in corpus: return v
    return "UNKNOWN_CONTINUITY_STATE"

replays = []
for m in manifests:
    state = classify(m)
    replays.append({
      "manifest_id": m["manifest_id"],
      "replay_summary": {
        "architecture_choices": m.get("electrical_dependencies", []) + m.get("electronics_dependencies", []),
        "protocol_selections": [x for x in m.get("electronics_dependencies", []) if x in {"spi", "i2c", "uart", "can"}],
        "topology_decisions": m.get("continuity_lineage", []),
        "power_tradeoffs": m.get("design_tradeoffs", []),
        "embedded_constraints": m.get("engineering_constraints", []),
        "numerical_approximations": m.get("mathematical_dependencies", []),
        "orchestration_logic": ["lineage-bound replay only"],
      },
      "divergence_classification": state,
      "determinism_note": "Derived strictly from manifest lineage; unknowns are explicitly classified.",
    })

(OUT / "engineering_reasoning_replay.json").write_text(json.dumps(replays, indent=2))
print(f"Replayed {len(replays)} manifests")
