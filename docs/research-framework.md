# Research Framework

This framework makes the operating thinking model explicit without altering source documents.

## 1) Observation

Capture the explicit claim, objective, or architecture statement from a source markdown file in its native wording and context.

## 2) Constraint Identification

Extract the limiting conditions that govern safe movement:

- technical limits
- process limits
- verification limits
- scope limits

These constraints are treated as first-class design inputs.

## 3) System Abstraction

Convert observation + constraints into reusable system primitives:

- inputs
- transformation stages
- control gates
- outputs
- failure modes

Abstractions are portable across domains (research, product, operations).

## 4) Execution Implication

Translate abstractions into concrete execution pathways linked to active engines:

- experiment pathways → KUP program
- decision logic pathways → decide.engine-tools
- deployment/computation pathways → Zayvora

---

## Constraint → Execution Pattern

`observation -> constraint -> dependency shape -> execution path -> measurement loop`

### Example

`API cost pressure -> budget constraint -> external inference dependency -> local-first inference strategy + tool routing -> measured latency/cost/reliability deltas in KUP and Zayvora runs`

This pattern is the framing layer used to interpret and route research into operational systems.
