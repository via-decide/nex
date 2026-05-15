# NEX Repository Execution Constitution

## Execution Pipeline
READ → ANALYZE → PLAN → VERIFY → MODIFY → REPLAY VALIDATE → COMMIT

## Continuity Rules
- Deterministic execution only: identical inputs must produce identical artifacts.
- Replay safety is mandatory for indexing, retrieval, caching, and synthesis outputs.
- Continuity lineage must be explicit in every generated artifact and diagnostic.
- Artifact persistence must use canonical locations and stable naming.
- Canonical ordering is required for serialized outputs (sorted keys/lists where applicable).

## Failure Rules
- **Bootstrap halt**: stop when required bootstrap files are missing or invalid.
- **Replay divergence**: mark run invalid when deterministic replay hashes mismatch.
- **Continuity corruption**: quarantine inconsistent lineage artifacts before further writes.
- **Artifact validation failure**: fail closed when schemas/state contracts are not met.

## Repository Constraints
- Prefer vanilla JS, HTML, CSS, Python utilities, and Markdown specs.
- Do not require build systems for bootstrap/continuity workflows.
- Preserve offline-capable, deterministic workstation behavior.
