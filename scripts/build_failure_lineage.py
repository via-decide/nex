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
    chain = m.get("failure_modes", []) or ["UNKNOWN_CONTINUITY_STATE"]
    prev = "thermal instability" if "thermal" in " ".join(m.get("engineering_constraints", [])).lower() else "engineering disturbance"
    node(prev, "origin")
    for item in chain:
        node(item, "failure"); edge(prev, item, "propagates_to"); prev = item
    node("orchestration divergence", "terminal"); edge(prev, "orchestration divergence", "can_lead_to")

edge_list = [{"from": a, "to": b, "relation": r, "edge_id": hashlib.md5(f"{a}|{b}|{r}".encode()).hexdigest()[:12]} for a,b,r in sorted(edges)]
(OUT / "failure_lineage_graph.json").write_text(json.dumps({"nodes": [nodes[k] for k in sorted(nodes)], "edges": edge_list}, indent=2))
print("failure_lineage/failure_lineage_graph.json generated")
