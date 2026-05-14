#!/usr/bin/env python3
"""
scripts/build_software_emergence_maps.py — Software Emergence Derivation Engine.
Generates deterministic derivation graphs showing how constraints force
the emergence of specific software abstractions and architectures.
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
OUTPUT_DIR = BASE_DIR / "software_emergence_maps"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("EmergenceEngine")

# ---------------------------------------------------------------------------
# DERIVATION DATA
# ---------------------------------------------------------------------------

EMERGENCE_TEMPLATES = [
    {
        "id": "package_management_emergence",
        "root_constraint": "larger_codebases",
        "steps": [
            {"constraint": "modularization pressure", "solution": "manual shared libs"},
            {"constraint": "version hell", "solution": "package managers"},
            {"constraint": "dependency graph complexity", "solution": "automated resolvers"},
            {"constraint": "runtime isolation", "solution": "plugin ecosystems"},
            {"constraint": "orchestration complexity", "solution": "containerization / k8s"}
        ],
        "lineage": "C -> M -> P -> D -> PE -> OC"
    },
    {
        "id": "desktop_runtime_emergence",
        "root_constraint": "browser_limitations",
        "steps": [
            {"constraint": "filesystem access requirement", "solution": "node.js integration"},
            {"constraint": "native windowing need", "solution": "Electron / NW.js"},
            {"constraint": "performance overhead", "solution": "VSCode-like optimized runtimes"},
            {"constraint": "extensibility pressure", "solution": "plugin-native workflows"},
            {"constraint": "memory footprint", "solution": "Tauri / local-first lightweight runtimes"}
        ],
        "lineage": "BL -> NI -> ER -> PNW -> LF"
    },
    {
        "id": "sovereign_runtime_emergence",
        "root_constraint": "cloud_dependency",
        "steps": [
            {"constraint": "offline failure", "solution": "local-first architectures"},
            {"constraint": "data ownership pressure", "solution": "sovereign identity / DIDs"},
            {"constraint": "vendor lock-in", "solution": "portable continuity manifests"},
            {"constraint": "execution fragility", "solution": "deterministic replay systems"},
            {"constraint": "trust centralization", "solution": "Zayvora / LogicHub authority"}
        ],
        "lineage": "CD -> LF -> SI -> PCM -> DR"
    }
]

# ---------------------------------------------------------------------------
# ENGINE
# ---------------------------------------------------------------------------

class EmergenceEngine:
    def build_maps(self):
        log.info("Generating Software Emergence Maps...")
        for template in EMERGENCE_TEMPLATES:
            map_data = {
                "metadata": {
                    "id": template["id"],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "engine_version": "1.0.0"
                },
                "root_constraint": template["root_constraint"],
                "derivation_graph": template["steps"],
                "lineage_string": template["lineage"]
            }
            
            filename = f"{template['id']}.json"
            filepath = OUTPUT_DIR / filename
            with open(filepath, "w") as f:
                json.dump(map_data, f, indent=2)
            log.info(f"Generated map: {filename}")

if __name__ == "__main__":
    engine = EmergenceEngine()
    engine.build_maps()
