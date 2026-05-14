#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INP = ROOT / "sync_models" / "networking_replay_manifests.json"
OUT = ROOT / "sync_models"; OUT.mkdir(parents=True, exist_ok=True)
man = json.loads(INP.read_text()) if INP.exists() else []
rows=[]
for i,m in enumerate(man,1):
    rows.append({"distributed_problem":f"distributed_continuity_case_{i}","network_constraints":m.get("replay_constraints",[]),"synchronization_constraints":m.get("synchronization_constraints",[]),"consensus_requirements":m.get("consensus_dependencies",[]),"authority_dependencies":m.get("authority_propagation",[]),"partition_scenarios":m.get("partition_recovery_rules",[]),"failure_modes":m.get("failure_modes",[]),"recovery_sequences":m.get("canonical_recovery_paths",[]),"continuity_requirements":m.get("continuity_lineage",[])})
(OUT/"distributed_sovereignty_dataset.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} distributed sovereignty records")
