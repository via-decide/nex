#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, OUT = ROOT / "metadata", ROOT / "engineering_graph"
OUT.mkdir(parents=True, exist_ok=True)

nodes, edges = {}, set()

def n(node_id: str, kind: str): nodes[node_id] = {"id": node_id, "kind": kind}
def e(a: str, b: str, rel: str): edges.add((a, b, rel))

for f in sorted(META.glob("*.semantic.json")):
    d = json.loads(f.read_text())
    for domain, items in sorted(d.items()):
        if isinstance(items, list):
            n(domain, "domain")
            for item in sorted(set(items)):
                n(item, "concept"); e(domain, item, "mentions")

for a, b in [("fourier transform", "dsp"), ("dsp", "rf systems"), ("rf systems", "signal compression"), ("control theory", "motor controllers"), ("control theory", "power regulation"), ("control theory", "autonomous systems")]:
    n(a, "math_or_control"); n(b, "engineering_stack"); e(a, b, "supports")

edge_list = [{"from": a, "to": b, "relation": r, "edge_id": hashlib.sha1(f"{a}|{b}|{r}".encode()).hexdigest()[:12]} for a,b,r in sorted(edges)]
(OUT / "graph.json").write_text(json.dumps({"nodes": [nodes[k] for k in sorted(nodes)], "edges": edge_list}, indent=2))
print("engineering_graph/graph.json generated")
