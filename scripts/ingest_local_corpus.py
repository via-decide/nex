#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT, META = ROOT / "corpus_text", ROOT / "metadata"

P = {
  "math_domains": [r"\b(fourier|laplace|z-transform|fft|optimization|gradient|convex|graph theory|queueing|numerical)\b", r"\$[^$]+\$|\\\([^)]+\\\)|\\\[[^]]+\\\]"],
  "engineering_constraints": [r"\b(voltage|current|power budget|thermal|ground(ing)?|emi|emc|ripple|slew rate)\b"],
  "failure_modes": [r"\b(oscillation|instability|fault|overheat|brownout|dropout|metastability|saturation)\b"],
  "control_primitives": [r"\b(pid|lqr|observer|kalman|state[- ]space|feedback|feedforward|controllability|stability margin)\b"],
  "electrical_concepts": [r"\b(power system|smart grid|energy flow|battery management|motor control|grounding strategy)\b"],
  "electronics_concepts": [r"\b(pcb|adc|dac|fpga|microcontroller|signal integrity|mixed-signal|analog front[- ]end|nvme|ssd|i2c|spi|uart|can)\b"],
  "systems_thinking": [r"\b(replay(able|ability)?|determinism|orchestration|distributed coordination|continuity|fault tolerance|graceful degradation)\b"],
}

def extract(text: str):
    s=text.lower(); out={}
    for k, patterns in P.items(): out[k]=sorted({m.group(0) for rx in patterns for m in re.finditer(rx, s)})
    return out

META.mkdir(parents=True, exist_ok=True)
for f in TXT.glob("*.txt"):
    payload = {"source": str(f), **extract(f.read_text(errors="ignore"))}
    (META / f"{f.stem}.semantic.json").write_text(json.dumps(payload, indent=2))
print("Engineering semantic mapping complete")
