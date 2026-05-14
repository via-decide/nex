#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
LIN = ROOT / "semantic_lineage" / "semantic_lineage_graph.json"
OUT = ROOT / "semantic_replay_vectors"; OUT.mkdir(parents=True, exist_ok=True)
g=json.loads(LIN.read_text()) if LIN.exists() else {"nodes":[]}
rows=[]
for i,n in enumerate(sorted([x["id"] for x in g.get("nodes",[])]),1):
    rows.append({"vector_id":hashlib.sha1(f"{n}|{i}".encode()).hexdigest()[:14],"source_nodes":[n],"reasoning_dependencies":["causal lineage","authority checks"],"continuity_constraints":["canonical consistency"],"authority_constraints":["execution cannot redefine truth"],"replay_requirements":["deterministic order","complete lineage"],"divergence_classes":["AUTHORITY_COLLAPSE","REPLAY_COLLAPSE"],"canonical_outputs":[f"preserved::{n}"]})
(OUT/"semantic_replay_vectors.json").write_text(json.dumps(rows,indent=2))
print(f"Generated {len(rows)} semantic replay vectors")
