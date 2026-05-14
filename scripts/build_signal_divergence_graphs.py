#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "signal_divergence_graphs"; OUT.mkdir(parents=True, exist_ok=True)
chain=["signal_noise","packet_corruption","synchronization_retry","queue_buildup","scheduler_instability","orchestration_divergence"]
classes=["THERMAL_DIVERGENCE","SIGNAL_NOISE_DIVERGENCE","CLOCK_DRIFT","POWER_INSTABILITY","LATENCY_DIVERGENCE","MEMORY_PRESSURE","ENERGY_COLLAPSE","UNKNOWN_PHYSICAL_STATE"]
nodes=[{"id":x,"kind":"signal_or_thermal"} for x in chain]
edges=[{"from":a,"to":b,"relation":"propagates_to","edge_id":hashlib.sha1(f'{a}|{b}'.encode()).hexdigest()[:12]} for a,b in zip(chain,chain[1:])]
(OUT/"signal_divergence_graph.json").write_text(json.dumps({"divergence_classes":classes,"nodes":nodes,"edges":edges},indent=2))
print("signal_divergence_graphs/signal_divergence_graph.json generated")
