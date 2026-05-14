#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, PROTO, TOPO, SYNC = [ROOT / d for d in ("distributed_raw", "distributed_text", "protocol_lineage", "network_topologies", "sync_models")]
for p in (RAW, TXT, PROTO, TOPO, SYNC): p.mkdir(parents=True, exist_ok=True)

docs = [
 {"title":"RFC and transport internals","text":"TCP/IP congestion control, QUIC streams, DNS authority, NAT traversal, routing convergence."},
 {"title":"Consensus and causality","text":"Raft leader election, Paxos quorum, vector clocks, append-only logs, event sourcing."},
 {"title":"Mesh sovereign sync","text":"Bluetooth mesh, LoRa peer routing, offline-first replication, CRDT conflict-free merges, local-first sync."},
]
manifest=[]
for i,d in enumerate(docs,1):
    sid=f"distributed_{i:04d}"; (RAW/f"{sid}.json").write_text(json.dumps(d,indent=2)); (TXT/f"{sid}.txt").write_text(d["text"])
    prot=[k for k in ["tcp/ip","quic","dns","raft","paxos","crdt","vector clocks","kafka","redis replication"] if k in d["text"].lower()]
    topo=["partition-aware", "offline-capable", "authority-propagating"]
    sync=["wal replay", "causal ordering", "reconciliation"]
    (PROTO/f"{sid}.json").write_text(json.dumps({"id":sid,"protocols":sorted(set(prot))},indent=2))
    (TOPO/f"{sid}.json").write_text(json.dumps({"id":sid,"topology":topo},indent=2))
    (SYNC/f"{sid}.json").write_text(json.dumps({"id":sid,"sync":sync},indent=2))
    manifest.append({"id":sid,"title":d["title"],"text":str(TXT/f"{sid}.txt"),"protocols":prot,"topology":topo,"sync":sync})

(ROOT/"metadata").mkdir(exist_ok=True)
(ROOT/"metadata"/"distributed_manifest.json").write_text(json.dumps(manifest,indent=2))
print(f"Harvested {len(manifest)} distributed artifacts")
