# Bootstrap Validation Semantics

## Validation States
- BOOTSTRAP_READY
- BOOTSTRAP_PARTIAL
- BOOTSTRAP_MISSING
- CONTINUITY_INITIALIZED
- SESSION_ACTIVE
- REPLAY_READY

## Deterministic Validation Rules
1. Inspect required files: `AGENTS.md`, `.codex/instructions.md`, `.codex/session.md`.
2. Verify continuity state fields exist in `.codex/session.md` and are non-empty.
3. Validate replay readiness by checking bootstrap state and protocol activation.
4. Preserve lineage integrity: validation output must include timestamp and state lineage.

## State Resolution Logic
- If zero required files exist → `BOOTSTRAP_MISSING`.
- If some but not all required files exist → `BOOTSTRAP_PARTIAL`.
- If all required files exist and continuity fields are valid → `BOOTSTRAP_READY` + `CONTINUITY_INITIALIZED` + `SESSION_ACTIVE`.
- If replay protocol is active with ready continuity state → `REPLAY_READY`.
