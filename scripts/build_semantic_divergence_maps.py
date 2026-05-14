#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "semantic_divergence_maps"; OUT.mkdir(parents=True, exist_ok=True)
chain=["payment_system","entitlement_mutation","ownership_revocation","canonical_corruption","sovereignty_failure"]
classes=["AUTHORITY_COLLAPSE","REPLAY_COLLAPSE","PROJECTION_LEAK","TRANSPORT_AUTHORITY_LEAK","ECONOMIC_AUTHORITY_LEAK","CONTRADICTION_SUPPRESSION","CANONICAL_DRIFT","UNKNOWN_SEMANTIC_STATE"]
(OUT/"semantic_divergence_map.json").write_text(json.dumps({"divergence_classes":classes,"nodes":[{"id":x,"kind":"semantic_divergence"} for x in chain],"edges":[{"from":a,"to":b,"relation":"propagates_to","edge_id":hashlib.sha1(f"{a}|{b}".encode()).hexdigest()[:12]} for a,b in zip(chain,chain[1:])]},indent=2))
print("semantic_divergence_maps/semantic_divergence_map.json generated")
