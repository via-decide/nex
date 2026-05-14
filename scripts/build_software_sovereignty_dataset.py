#!/usr/bin/env python3
"""
scripts/build_software_sovereignty_dataset.py — Sovereign Software Dataset Builder.
Generates deterministic software engineering cognition datasets.
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
OUTPUT_FILE = BASE_DIR / "software_sovereignty_cognition_v1.0.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("DatasetBuilder")

# ---------------------------------------------------------------------------
# DATASET TEMPLATES
# ---------------------------------------------------------------------------

DATA_SAMPLES = [
    {
        "software_problem": "Design a persistent code editor that operates without a central server.",
        "workflow_constraints": ["offline-first", "sync on reconnect", "multi-device"],
        "runtime_constraints": ["local filesystem access", "low memory footprint"],
        "continuity_requirements": ["immutable save-states", "versioned history"],
        "plugin_dependencies": ["language server protocol", "vcs integration"],
        "ecosystem_pressures": ["sovereignty_pressure", "persistence_pressure"],
        "failure_modes": ["state_divergence", "continuity_break"],
        "lockin_risks": ["proprietary sync formats", "cloud-only plugins"],
        "sovereignty_requirements": ["local-first storage", "self-signed identities"],
        "replay_constraints": ["deterministic file ops"]
    },
    {
        "software_problem": "Migrate a plugin-heavy IDE from Electron to a native Rust-based runtime.",
        "workflow_constraints": ["preserve existing shortcuts", "zero latency"],
        "runtime_constraints": ["memory cap 500MB", "native UI components"],
        "continuity_requirements": ["plugin state migration", "workspace persistence"],
        "plugin_dependencies": ["js-to-rust bridge", "sandboxed execution"],
        "ecosystem_pressures": ["fragmentation_pressure", "workflow_pressure"],
        "failure_modes": ["plugin_collapse", "runtime_fragmentation"],
        "lockin_risks": ["runtime-specific APIs", "non-portable plugin hooks"],
        "sovereignty_requirements": ["open-standard plugin ABI", "portable config"],
        "replay_constraints": ["causal event ordering"]
    }
]

# ---------------------------------------------------------------------------
# BUILDER
# ---------------------------------------------------------------------------

class DatasetBuilder:
    def build_dataset(self):
        log.info(f"Building Sovereign Software Dataset: {OUTPUT_FILE}")
        
        with open(OUTPUT_FILE, "w") as f:
            for sample in DATA_SAMPLES:
                sample["metadata"] = {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0.0"
                }
                f.write(json.dumps(sample) + "\n")
        
        log.info(f"Dataset complete. Total records: {len(DATA_SAMPLES)}")

if __name__ == "__main__":
    builder = DatasetBuilder()
    builder.build_dataset()
