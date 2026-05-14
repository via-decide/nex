#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "replay_manifests" / "replay_manifests.json"
OUT = ROOT / "failure_lineage"; OUT.mkdir(parents=True, exist_ok=True)
manifests = json.loads(INP.read_text()) if INP.exists() else []

nodes, edges = {}, set()
def node(name, kind): nodes[name] = {"id": name, "kind": kind}
def edge(a, b, rel): edges.add((a, b, rel))

for m in manifests:
    assumptions = sorted(set(m.get("mathematical_dependencies", []))) or ["mathematical assumption"]
    failures = sorted(set(m.get("failure_modes", []))) or ["UNKNOWN_CONTINUITY_STATE"]
    start = "thermal instability" if any("thermal" in c.lower() for c in m.get("engineering_constraints", [])) else "engineering disturbance"
    node(start, "origin"); prev = start
    for a in assumptions: node(a, "math_assumption"); edge(prev, a, "depends_on"); prev = a
    for f in failures: node(f, "failure"); edge(prev, f, "propagates_to"); prev = f
    hw = sorted(set(m.get("electronics_dependencies", []) + m.get("electrical_dependencies", []))) or ["hardware boundary"]
    for h in hw: node(h, "hardware"); edge(prev, h, "affects"); prev = h
    node("orchestration divergence", "terminal"); edge(prev, "orchestration divergence", "can_lead_to")

edge_list = [{"from": a, "to": b, "relation": r, "edge_id": hashlib.sha1(f"{a}|{b}|{r}".encode()).hexdigest()[:12]} for a,b,r in sorted(edges)]
(OUT / "failure_lineage_graph.json").write_text(json.dumps({"nodes": [nodes[k] for k in sorted(nodes)], "edges": edge_list}, indent=2))
print("failure_lineage/failure_lineage_graph.json generated")
