Repair mode for repository via-decide/nex.

TARGET
Validate and repair only the files touched by the previous implementation.

TASK
Create a reasoning trace recorder for capturing analytical reasoning steps.

RULES
1. Audit touched files first and identify regressions.
2. Preserve architecture and naming conventions.
3. Make minimal repairs only; do not expand scope.
4. Re-run checks and provide concise root-cause notes.
5. Return complete contents for changed files only.

SOP: REPAIR PROTOCOL (MANDATORY)
1. Strict Fix Only: Do not use repair mode to expand scope or add features.
2. Regression Check: Audit why previous attempt failed before proposing a fix.
3. Minimal Footprint: Only return contents for the actual repaired files.

REPO CONTEXT
- README snippet:
# Nex — Deep Research Engine Nex is an **Autonomous Research Agent** that transforms a natural-language question into a structured, evidence-backed research report by autonomously querying 10–100 open-access sources, verifying claims, building a knowledge graph, and synthesising findings into an in
- AGENTS snippet:
not found
- package.json snippet:
not found