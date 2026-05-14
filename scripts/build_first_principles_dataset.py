#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "architecture_derivations" / "architecture_replay.json"
OUT = ROOT / "architecture_derivations"; OUT.mkdir(parents=True, exist_ok=True)
replays = json.loads(INP.read_text()) if INP.exists() else []
rows=[]
for i,r in enumerate(replays,1):
    rows.append({"engineering_problem":f"first_principles_case_{i}","primitive_constraints":["latency floor","memory ceiling","sync delay"],"mathematical_dependencies":["graph theory","optimization","numerical stability"],"physical_constraints":["thermal limit","voltage stability","bandwidth ceiling"],"continuity_pressures":["replay pressure","orchestration pressure"],"tradeoff_surfaces":["throughput vs determinism","memory vs accuracy"],"architecture_emergence":r.get("causal_chain",[]),"failure_boundaries":["continuity collapse","authority collapse"],"replay_constraints":["causal order preservation","append-only lineage"],"sovereignty_requirements":["local-first execution","runtime replaceability"]})
(OUT/"first_principles_dataset.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} first-principles dataset rows")
