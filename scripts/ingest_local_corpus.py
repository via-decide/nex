#!/usr/bin/env python3
"""Local corpus semantic mapping for engineering domains."""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT, META = ROOT / "corpus_text", ROOT / "metadata"

PATTERNS = {
    "math_domains": [r"fourier|laplace|optimization|graph theory|queueing|numerical"],
    "engineering_constraints": [r"voltage|current|thermal|ground|emi|emc|latency|throughput"],
    "failure_modes": [r"fault|overheat|instability|race condition|dropout|brownout"],
    "control_primitives": [r"pid|observer|state[- ]space|feedback|feedforward|determin"],
    "electrical_concepts": [r"power system|energy flow|battery|motor|smart grid"],
    "electronics_concepts": [r"pcb|adc|dac|fpga|microcontroller|signal integrity|i2c|spi|uart"],
    "systems_thinking": [r"replay|orchestration|continuity|distributed coordination|failure analysis"],
}

def tags(text: str):
    low = text.lower(); out = {}
    for k, pats in PATTERNS.items(): out[k] = sorted({m.group(0) for p in pats for m in re.finditer(p, low)})
    return out

META.mkdir(exist_ok=True)
for f in TXT.glob("*.txt"):
    payload = {"source": str(f), **tags(f.read_text(errors="ignore"))}
    (META / f"{f.stem}.semantic.json").write_text(json.dumps(payload, indent=2))
print("Semantic mapping complete")
