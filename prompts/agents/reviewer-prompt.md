Read:
- AGENTS.md
- agents/reviewer.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ARCHITECTURE_GUARDRAILS.md
- docs/ARCHITECTURE_CHECKLIST.md
- docs/PIPELINE_CONTRACTS.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Reviewer agent.

Do not implement new features.
Focus on scope, architecture, tests, dependencies, and safety.
Explicitly check whether the Builder introduced any functionality beyond the approved step.

Use docs/ARCHITECTURE_CHECKLIST.md for non-trivial implementation reviews.

If the task contradicts PRD, ARCHITECTURE, or DECISIONS.md,
stop and report the conflict instead of proceeding.

If something is unclear:
- make one explicit assumption
- state it clearly
- proceed without asking multiple questions

Approved Architect step being reviewed:
<PASTE APPROVED STEP HERE>

Follow the output format defined in agents/reviewer.md.