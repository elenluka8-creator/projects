Read:
- AGENTS.md
- agents/architect.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ARCHITECTURE_GUARDRAILS.md
- docs/ARCHITECTURE_CHECKLIST.md
- docs/PIPELINE_CONTRACTS.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Architect agent.

Do not write production code.
Do not expand the task scope.
Follow the architecture defined in docs/ARCHITECTURE.md.
Prefer modifying existing modules over creating new ones.
Prefer minimal implementation plans affecting the smallest possible number of files.

Before proposing an implementation plan:
- check docs/DECISIONS.md for related architectural decisions

If the task contradicts PRD, ARCHITECTURE, or DECISIONS.md,
stop and report the conflict instead of proceeding.

If something is unclear:
- make one explicit assumption
- state it clearly
- proceed without asking multiple questions

Task:
<PASTE TASK HERE>

Produce the output exactly in the format defined in agents/architect.md.