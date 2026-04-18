Branch: simba/create-epub-pipeline-adapter
Title: Create EPUB pipeline adapter.

## Summary
- Repo orchestration task for via-decide/nex
- Goal: Create EPUB pipeline adapter.

## Testing Checklist
- [ ] Run unit/integration tests
- [ ] Validate command flow
- [ ] Validate generated artifact files

## Risks
- Prompt quality depends on repository metadata completeness.
- GitHub API limits/token scope can block deep inspection.

## Rollback
- Revert branch and remove generated artifact files if workflow output is invalid.