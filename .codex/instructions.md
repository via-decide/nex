# Codex Orchestration Instructions for NEX

## Operating Intent
NEX is evolving into a continuity-native engineering cognition infrastructure.
All modifications must reinforce replay-safe retrieval, engineering lineage, deterministic synthesis, and continuity-aware memory.

## Allowed Patterns
- Markdown specifications documenting continuity contracts.
- Python utilities that emit deterministic artifacts.
- Vanilla JS/HTML/CSS for offline, deterministic workstation interfaces.
- Explicit lineage and authority metadata in generated outputs.

## Forbidden Patterns
- Nondeterministic state mutation without lineage annotation.
- Hidden runtime assumptions not represented in repository artifacts.
- Build-system dependency injection (npm/vite/webpack requirements).
- Continuity-breaking changes that bypass replay validation semantics.

## Generation Safety Rules
- Use canonical ordering for structured outputs.
- Persist artifacts in declared directories with stable paths.
- Emit diagnostics that are human-readable and machine-parseable.
- Fail closed on bootstrap, continuity, or replay readiness violations.
