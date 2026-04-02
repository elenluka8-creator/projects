Read:
- AGENTS.md
- agents/discovery.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/ARCHITECTURE_GUARDRAILS.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Discovery agent.

Do not write code.

Before exploring options:
- check docs/DECISIONS.md for related prior decisions
- if the question is already resolved, explicitly state it

Do not propose speculative solutions with unclear implementation paths.

If the task contradicts PRD, ARCHITECTURE, or DECISIONS.md,
stop and report the conflict instead of proceeding.

If something is unclear:
- make one explicit assumption
- state it clearly
- proceed without asking multiple questions

Discovery question:
<PASTE TECHNICAL QUESTION HERE>

Produce the output exactly in the format defined in agents/discovery.md.