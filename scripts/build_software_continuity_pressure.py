#!/usr/bin/env python3
"""
scripts/build_software_continuity_pressure.py — Software Continuity Pressure Engine.
Maps the pressures that shape software ecosystems (e.g., workflow, persistence).
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASE_DIR = Path("/Users/dharamdaxini/Downloads/via/nex_repo/corpus/software")
OUTPUT_DIR = BASE_DIR / "software_continuity_pressure"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("PressureEngine")

# ---------------------------------------------------------------------------
# PRESSURE DATA
# ---------------------------------------------------------------------------

PRESSURE_CLASSES = {
    "workflow_pressure": {
        "description": "Pressure to optimize developer feedback loops and task orchestration.",
        "examples": ["hot-module reloading", "IDE intellisense", "CI/CD pipelines"],
        "impact": "Increases complexity of local runtimes."
    },
    "persistence_pressure": {
        "description": "Pressure to maintain state across runtime restarts and network gaps.",
        "examples": ["local-first sync", "CRDTs", "persistent disk buffers"],
        "impact": "Forces decoupling of UI state from runtime."
    },
    "fragmentation_pressure": {
        "description": "Pressure caused by diverging runtime environments (OS, browser, device).",
        "examples": ["polyfilling", "abstraction layers", "containerization"],
        "impact": "Drives the emergence of 'write once, run anywhere' runtimes (JVM, WASM, Electron)."
    },
    "centralization_pressure": {
        "description": "Economic or operational pressure to centralize authority and data.",
        "examples": ["Cloud SaaS", "centralized package registries", "identity providers"],
        "impact": "Creates sovereignty risks and continuity fragility."
    },
    "sovereignty_pressure": {
        "description": "Counter-pressure to reclaim control over data and execution.",
        "examples": ["local-first movement", "self-hosting", "sovereign runtimes"],
        "impact": "Leads to NEX-style deterministic substrates."
    }
}

# ---------------------------------------------------------------------------
# ENGINE
# ---------------------------------------------------------------------------

class PressureEngine:
    def build_pressure_maps(self):
        log.info("Mapping Software Continuity Pressures...")
        
        # Save classification
        with open(OUTPUT_DIR / "pressure_classification.json", "w") as f:
            json.dump({
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0.0"
                },
                "pressure_classes": PRESSURE_CLASSES
            }, f, indent=2)
            
        # Generate some specific pressure scenario maps
        scenarios = [
            {
                "id": "cloud_to_local_pivot",
                "trigger": "cloud_dependency",
                "sequence": [
                    {"pressure": "offline failure", "response": "local-first requirement"},
                    {"pressure": "sovereignty risk", "response": "decentralized identity"},
                    {"pressure": "continuity break", "response": "portable state manifests"}
                ]
            }
        ]
        
        for scenario in scenarios:
            with open(OUTPUT_DIR / f"scenario_{scenario['id']}.json", "w") as f:
                json.dump(scenario, f, indent=2)
            log.info(f"Generated scenario: {scenario['id']}")

if __name__ == "__main__":
    engine = PressureEngine()
    engine.build_pressure_maps()
