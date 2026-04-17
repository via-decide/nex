Branch: simba/create-research-note-linker
Title: Create research note linker.

## Summary
- Repo orchestration task for via-decide/nex
- Goal: Create research note linker.

## Testing Checklist
- [ ] Run unit/integration tests
- [ ] Validate command flow
- [ ] Validate generated artifact files

## Risks
- Prompt quality depends on repository metadata completeness.
- GitHub API limits/token scope can block deep inspection.

## Rollback
- Revert branch and remove generated artifact files if workflow output is invalid.