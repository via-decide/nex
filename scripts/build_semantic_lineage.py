#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "semantic_lineage"; OUT.mkdir(parents=True, exist_ok=True)
seed=[("authority","admissibility"),("admissibility","replay_validation"),("replay_validation","canonical_continuity"),("canonical_continuity","sovereignty_preservation")]
nodes={x for e in seed for x in e}
edges=[{"from":a,"to":b,"relation":"supports","edge_id":hashlib.sha1(f"{a}|{b}".encode()).hexdigest()[:12]} for a,b in seed]
(OUT/"semantic_lineage_graph.json").write_text(json.dumps({"lineage_types":["engineering","authority","replay","infrastructure","civilization","runtime","mathematical"],"nodes":[{"id":n,"kind":"semantic"} for n in sorted(nodes)],"edges":edges},indent=2))
print("semantic_lineage/semantic_lineage_graph.json generated")
