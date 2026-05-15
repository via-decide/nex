#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "semantic_replay_vectors" / "semantic_replay_vectors.json"
OUT = ROOT / "semantic_replay_vectors"; OUT.mkdir(parents=True, exist_ok=True)
vec=json.loads(INP.read_text()) if INP.exists() else []
rows=[]
for i,v in enumerate(vec,1):
    rows.append({"semantic_problem":f"semantic_continuity_case_{i}","authority_constraints":v.get("authority_constraints",[]),"continuity_constraints":v.get("continuity_constraints",[]),"replay_constraints":v.get("replay_requirements",[]),"contradictions":["preserve incompatible truths by assumption domain"],"divergence_risks":v.get("divergence_classes",[]),"canonical_requirements":["lineage-complete replay","authority validation"],"sovereignty_requirements":["local-first storage","non-centralized truth control"]})
(OUT/"semantic_sovereignty_dataset.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} semantic sovereignty rows")
