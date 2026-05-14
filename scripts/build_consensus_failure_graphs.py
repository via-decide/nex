#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "metadata" / "distributed_manifest.json"
OUT = ROOT / "consensus_failure_graphs"; OUT.mkdir(parents=True, exist_ok=True)
items = json.loads(MAN.read_text()) if MAN.exists() else []

nodes,edges={},set()
def n(v,t): nodes[v]={"id":v,"kind":t}
def e(a,b,r): edges.add((a,b,r))
for _ in items:
    chain=["network_partition","stale_leader_election","conflicting_writes","causality_divergence","reconciliation_pressure","canonical_replay_validation"]
    for c in chain: n(c,"failure")
    for a,b in zip(chain,chain[1:]): e(a,b,"propagates_to")

(OUT/"consensus_failure_graph.json").write_text(json.dumps({"nodes":[nodes[k] for k in sorted(nodes)],"edges":[{"from":a,"to":b,"relation":r,"edge_id":hashlib.sha1(f'{a}|{b}|{r}'.encode()).hexdigest()[:12]} for a,b,r in sorted(edges)]},indent=2))
print("consensus_failure_graphs/consensus_failure_graph.json generated")
