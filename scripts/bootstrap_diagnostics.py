#!/usr/bin/env python3
"""Deterministic bootstrap diagnostics for NEX continuity initialization."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    ROOT / "AGENTS.md",
    ROOT / ".codex" / "instructions.md",
    ROOT / ".codex" / "session.md",
]
OUT_DIR = ROOT / "bootstrap_diagnostics"
OUT_FILE = OUT_DIR / "bootstrap_diagnostics.json"


def compute_state(present_count: int) -> str:
    if present_count == 0:
        return "BOOTSTRAP_MISSING"
    if present_count < len(REQUIRED):
        return "BOOTSTRAP_PARTIAL"
    return "CONTINUITY_INITIALIZED"


def main() -> None:
    checks = {str(path.relative_to(ROOT)): path.exists() for path in REQUIRED}
    present = sum(1 for v in checks.values() if v)
    state = compute_state(present)
    replay_ready = present == len(REQUIRED)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "state": state,
        "pipeline": "repository unlocked" if replay_ready else "repository blocked",
        "replay": "ready" if replay_ready else "not_ready",
        "validation_states": sorted(
            set(
                [state]
                + (["BOOTSTRAP_READY", "SESSION_ACTIVE", "REPLAY_READY"] if replay_ready else [])
            )
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("[BOOTSTRAP]")
    print(f"AGENTS.md {'✓' if checks['AGENTS.md'] else '✗'}")
    print(f"instructions.md {'✓' if checks['.codex/instructions.md'] else '✗'}")
    print(f"session.md {'✓' if checks['.codex/session.md'] else '✗'}")
    print("\n[STATE]")
    print(state)
    print("\n[PIPELINE]")
    print(report["pipeline"])
    print("\n[REPLAY]")
    print(report["replay"])


if __name__ == "__main__":
    main()
