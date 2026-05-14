#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, TOPO, MEM, LIN = [ROOT / d for d in ("ai_runtime_raw", "ai_runtime_text", "runtime_topologies", "memory_constraints", "inference_lineage")]
for p in (RAW, TXT, TOPO, MEM, LIN): p.mkdir(parents=True, exist_ok=True)

docs = [
 {"title":"Portable runtimes","text":"llama.cpp GGUF CPU fallback, Ollama runtime swaps, ONNX Runtime execution providers, MLX local inference."},
 {"title":"GPU scheduling and KV cache","text":"vLLM paged attention, TensorRT kernels, KV-cache eviction, batching scheduler, NUMA memory boundaries."},
 {"title":"Distributed inference continuity","text":"model sharding, speculative decoding, replay-safe orchestration, quantization Q4/Q8 drift checks."},
]
manifest=[]
for i,d in enumerate(docs,1):
    sid=f"ai_runtime_{i:04d}"; (RAW/f"{sid}.json").write_text(json.dumps(d,indent=2)); (TXT/f"{sid}.txt").write_text(d["text"])
    topo=["runtime_substitution", "scheduler_chain", "offline_local_first"]
    mem=["kv_cache_budget", "gpu_memory_ceiling", "numa_affinity"]
    lin=["replay_boundary", "continuity_check", "canonical_restore"]
    (TOPO/f"{sid}.json").write_text(json.dumps({"id":sid,"topology":topo},indent=2))
    (MEM/f"{sid}.json").write_text(json.dumps({"id":sid,"memory":mem},indent=2))
    (LIN/f"{sid}.json").write_text(json.dumps({"id":sid,"lineage":lin},indent=2))
    manifest.append({"id":sid,"title":d["title"],"text":str(TXT/f"{sid}.txt"),"topology":topo,"memory":mem,"lineage":lin})

(ROOT/"metadata").mkdir(exist_ok=True)
(ROOT/"metadata"/"ai_runtime_manifest.json").write_text(json.dumps(manifest,indent=2))
print(f"Harvested {len(manifest)} ai runtime artifacts")
