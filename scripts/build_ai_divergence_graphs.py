#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "ai_runtime_manifest.json"
OUT = ROOT / "ai_divergence_graphs"; OUT.mkdir(parents=True, exist_ok=True)
_ = json.loads(MAN.read_text()) if MAN.exists() else []
chain=["gpu_memory_exhaustion","kv_cache_eviction","context_truncation","reasoning_degradation","replay_divergence","continuity_classification"]
nodes=[{"id":c,"kind":"divergence"} for c in chain]
edges=[{"from":a,"to":b,"relation":"propagates_to","edge_id":hashlib.sha1(f'{a}|{b}'.encode()).hexdigest()[:12]} for a,b in zip(chain,chain[1:])]
(OUT/"ai_divergence_graph.json").write_text(json.dumps({"nodes":nodes,"edges":edges},indent=2))
print("ai_divergence_graphs/ai_divergence_graph.json generated")
