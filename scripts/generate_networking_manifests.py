#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "distributed_manifest.json"
OUT = ROOT / "sync_models"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []
rows=[]
for x in sorted(items,key=lambda y:y["id"]):
    rows.append({
      "network_topology":"mesh_partition_tolerant" if "mesh" in x["title"].lower() else "replicated_log_topology",
      "synchronization_constraints":["bounded replication lag","offline replay admissibility"],
      "consensus_dependencies":["raft quorum","paxos safety"],
      "authority_propagation":["leader lease","epoch transition"],
      "partition_recovery_rules":["fence stale writers","reconcile via vector clocks"],
      "replay_constraints":["append-only wal","deterministic ordering"],
      "failure_modes":["split-brain","causal reorder","stale read"],
      "continuity_lineage":x.get("sync",[]),
      "canonical_recovery_paths":["quorum restore","log replay","state checksum validation"]
    })
(OUT/"networking_replay_manifests.json").write_text(json.dumps(rows,indent=2))
print(f"Generated {len(rows)} networking manifests")
