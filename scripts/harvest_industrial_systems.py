#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, PROTO, SAFE, LIN = [ROOT / d for d in ("industrial_raw", "industrial_text", "industrial_protocols", "industrial_safety", "industrial_lineage")]
for p in (RAW, TXT, PROTO, SAFE, LIN): p.mkdir(parents=True, exist_ok=True)

SEED_DOCS = [
    {"title":"PLC SCADA coordination baseline","text":"PLC ladder logic, SCADA supervision, DCS transitions, Modbus and OPC-UA polling with RS-485 safety interlocks."},
    {"title":"Robotics conveyor orchestration","text":"EtherCAT motion control, CAN bus actuator feedback, CNC path planning, conveyor synchronization."},
    {"title":"Safety standard lineage","text":"IEC 61508 SIL analysis, ISO 26262 fail-safe redundancy, emergency stop authority transitions."},
]
PROTOCOLS = ["modbus", "opc-ua", "can bus", "ethercat", "profinet", "rs-485", "bacnet"]

manifest = []
for i, doc in enumerate(SEED_DOCS, start=1):
    stem = f"industrial_{i:04d}"; raw = RAW / f"{stem}.json"; txt = TXT / f"{stem}.txt"
    raw.write_text(json.dumps(doc, indent=2)); txt.write_text(doc["text"])
    protocols = sorted({p for p in PROTOCOLS if p in doc["text"].lower()})
    (PROTO / f"{stem}.protocols.json").write_text(json.dumps({"title": doc["title"], "protocols": protocols}, indent=2))
    safety_terms = sorted(set(re.findall(r"IEC 61508|ISO 26262|SIL|fail-safe|redundancy|emergency", doc["text"], flags=re.I)))
    (SAFE / f"{stem}.safety.json").write_text(json.dumps({"title": doc["title"], "safety_terms": safety_terms}, indent=2))
    lineage = ["operator_authority", "safety_override", "restart_sequence"] if "emergency" in doc["text"].lower() else ["process_sync", "state_transition"]
    (LIN / f"{stem}.lineage.json").write_text(json.dumps({"title": doc["title"], "lineage": lineage}, indent=2))
    manifest.append({"id": stem, "title": doc["title"], "raw": str(raw), "text": str(txt), "protocols": protocols, "lineage": lineage})

(ROOT / "metadata").mkdir(exist_ok=True)
(ROOT / "metadata" / "industrial_manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"Harvested {len(manifest)} industrial documents")
