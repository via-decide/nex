#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "industrial_manifest.json"
OUT = ROOT / "industrial_failure_graphs"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []

nodes, edges = {}, set()
def n(x,t): nodes[x] = {"id": x, "kind": t}
def e(a,b,r): edges.add((a,b,r))

for item in items:
    chain = ["sensor_noise", "unstable_pid_correction", "motor_oscillation", "thermal_rise", "emergency_cutoff", "production_halt"]
    if "scada" in item["title"].lower(): chain = ["sync_timeout", "actuator_divergence", "timing_failure", "safety_override", "production_halt"]
    for i, step in enumerate(chain): n(step, "failure");
    for a,b in zip(chain, chain[1:]): e(a,b,"propagates_to")

graph = {"nodes": [nodes[k] for k in sorted(nodes)], "edges": [{"from": a, "to": b, "relation": r, "edge_id": hashlib.sha1(f"{a}|{b}|{r}".encode()).hexdigest()[:12]} for a,b,r in sorted(edges)]}
(OUT / "safety_failure_graph.json").write_text(json.dumps(graph, indent=2))
print("industrial_failure_graphs/safety_failure_graph.json generated")
