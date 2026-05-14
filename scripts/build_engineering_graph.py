#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META, OUT = ROOT / "metadata", ROOT / "engineering_graph"
OUT.mkdir(exist_ok=True)
nodes, edges = {}, []

def add_node(name, kind): nodes.setdefault(name, {"id": name, "kind": kind})
def link(a, b, rel): edges.append({"from": a, "to": b, "relation": rel})

for f in META.glob("*.semantic.json"):
    d = json.loads(f.read_text())
    for domain, items in d.items():
        if isinstance(items, list):
            add_node(domain, "domain")
            for it in items: add_node(it, "concept"); link(domain, it, "mentions")

for a,b in [("fourier","signal integrity"),("control","motor"),("optimization","power system")]:
    add_node(a,"math"); add_node(b,"engineering"); link(a,b,"supports")

(OUT/"graph.json").write_text(json.dumps({"nodes": list(nodes.values()), "edges": edges}, indent=2))
print("engineering_graph/graph.json generated")
