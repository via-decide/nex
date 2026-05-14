#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contradictions"; OUT.mkdir(parents=True, exist_ok=True)
rows=[
 {"contradiction_id":"c1","class":"infrastructure contradiction","claim_a":"cloud improves scalability","claim_b":"cloud reduces sovereignty","assumptions":["global latency tolerance","external authority trust"]},
 {"contradiction_id":"c2","class":"replay contradiction","claim_a":"high throughput via async mutation","claim_b":"deterministic replay requires causal ordering","assumptions":["ordering metadata present","reconciliation budget"]}
]
(OUT/"contradiction_artifacts.json").write_text(json.dumps(rows,indent=2))
print(f"Wrote {len(rows)} contradiction artifacts")
