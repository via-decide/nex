Branch: simba/create-cross-source-comparator
Title: Create cross-source comparator.

## Summary
- Repo orchestration task for via-decide/nex
- Goal: Create cross-source comparator.

## Testing Checklist
- [ ] Run unit/integration tests
- [ ] Validate command flow
- [ ] Validate generated artifact files

## Risks
- Prompt quality depends on repository metadata completeness.
- GitHub API limits/token scope can block deep inspection.

## Rollback
- Revert branch and remove generated artifact files if workflow output is invalid.