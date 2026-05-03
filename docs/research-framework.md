# Research Framework

Explicit model for how NEX transforms raw markdown into executable system intelligence.

## 1) Observation

Capture what the document is asserting, designing, or constraining in its native wording.

- preserve author intent
- preserve contextual boundaries
- avoid interpretive rewriting

## 2) Constraint Identification

Identify limiting forces that govern viable execution.

- resource limits (cost, latency, infrastructure)
- process limits (scope, sequencing, ownership)
- verification limits (evidence quality, testability)
- integration limits (engine compatibility, dependency shape)

## 3) System Abstraction

Convert observation + constraints into reusable system primitives.

- input assumptions
- transformation path
- control gates
- outputs
- measurable failure modes

This abstraction is the bridge layer between research artifacts and operational engines.

## 4) Execution Implication

Route each abstraction to concrete execution surfaces.

- experiment orchestration -> **KUP**
- decision logic instrumentation -> **Decide engines**
- deployment/action pathways -> **Zayvora**

---

## Constraint-Driven Pattern

`observation -> constraint -> system dependency -> execution route -> measurement loop`

### Example Path

`API cost pressure -> budget constraint -> external model dependency risk -> local inference + selective tool routing -> latency/cost/reliability measurement across KUP runs and Zayvora execution`
