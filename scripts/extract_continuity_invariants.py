#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "continuity_invariants"; OUT.mkdir(parents=True, exist_ok=True)
rows=[
 {"class":"AUTHORITY","law":"execution cannot redefine truth"},
 {"class":"REPLAY","law":"if you cannot replay it, you do not control it"},
 {"class":"CONTINUITY","law":"causal lineage must survive replacement"},
 {"class":"DIVERGENCE","law":"suppressed contradiction causes canonical drift"}
]
(OUT/"invariants.json").write_text(json.dumps({"bundle_id":"vialogic-invariants-v1","invariants":rows},indent=2))
print("continuity_invariants/invariants.json generated")
