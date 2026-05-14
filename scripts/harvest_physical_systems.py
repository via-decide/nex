#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, MATH, SIG, THERMO, ENERGY, DIV = [ROOT / d for d in ("physical_raw", "physical_text", "mathematical_lineage", "signal_constraints", "thermodynamic_maps", "energy_continuity", "physical_divergence_maps")]
for p in (RAW, TXT, MATH, SIG, THERMO, ENERGY, DIV): p.mkdir(parents=True, exist_ok=True)

docs=[
 {"title":"Math as infrastructure substrate","text":"linear algebra, graph theory, probability, information theory, optimization, fourier transforms, numerical stability."},
 {"title":"Physics shaping computation","text":"thermodynamics, electromagnetism, signal propagation, noise, semiconductor heat transfer, wave limits."},
 {"title":"Engineering physics continuity","text":"cpu thermals, gpu memory bandwidth, clock synchronization drift, voltage stability, timing pressure."},
]
manifest=[]
for i,d in enumerate(docs,1):
    sid=f"phys_{i:04d}"; (RAW/f"{sid}.json").write_text(json.dumps(d,indent=2)); (TXT/f"{sid}.txt").write_text(d["text"])
    math=["linear_algebra","graph_theory","information_theory","optimization"]
    signal=["signal_to_noise_limit","clock_jitter","latency_floor"]
    thermo=["thermal_density_limit","heat_dissipation_pressure","power_to_heat_coupling"]
    energy=["finite_energy_budget","bandwidth_energy_tradeoff","sustained_power_window"]
    div=["thermal_divergence_risk","signal_noise_divergence","sync_instability"]
    (MATH/f"{sid}.json").write_text(json.dumps({"id":sid,"math":math},indent=2)); (SIG/f"{sid}.json").write_text(json.dumps({"id":sid,"signal":signal},indent=2)); (THERMO/f"{sid}.json").write_text(json.dumps({"id":sid,"thermo":thermo},indent=2)); (ENERGY/f"{sid}.json").write_text(json.dumps({"id":sid,"energy":energy},indent=2)); (DIV/f"{sid}.json").write_text(json.dumps({"id":sid,"divergence":div},indent=2))
    manifest.append({"id":sid,"title":d["title"],"text":str(TXT/f"{sid}.txt"),"math":math,"signal":signal,"thermo":thermo,"energy":energy,"divergence":div})

(ROOT/"metadata").mkdir(exist_ok=True)
(ROOT/"metadata"/"physical_manifest.json").write_text(json.dumps(manifest,indent=2))
print(f"Harvested {len(manifest)} physical systems artifacts")
