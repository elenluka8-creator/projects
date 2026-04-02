# Agent Prompt Templates

This directory contains prompt templates used to run the project agents defined in `AGENTS.md`.

Agents help structure AI-assisted development so that implementation remains predictable,
aligned with the architecture, and easy to review.

Before running any agent, read the project documentation:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_GUARDRAILS.md`
- `docs/ARCHITECTURE_CHECKLIST.md`
- `docs/PIPELINE_CONTRACTS.md`
- `docs/TASKS.md`
- `docs/DECISIONS.md`

Agents must also follow the global rules defined in:

- `.cursor/rules.md`
- `CLAUDE.md`

---

# Agent Overview

The project defines five agents:

| Agent     | Role                                                   |
|-----------|--------------------------------------------------------|
| Discovery | Explore technical approaches and recommend a direction |
| Product   | Turn feature ideas into specifications and tasks       |
| Architect | Produce an implementation plan                         |
| Builder   | Implement the approved plan                            |
| Reviewer  | Validate implementation against the plan               |

Each agent has a dedicated prompt template in this directory.

---

# How to Choose an Agent

Choose the first agent based on the nature of the request.

## Discovery

Use Discovery when there is **technical uncertainty**.

Examples:

- choosing between multiple libraries
- deciding architecture approaches
- evaluating trade-offs
- revisiting a past decision

Typical questions:

- Should the MVP support TXT only or TXT + EPUB?
- Should prompts live in files or code?
- Do we need an abstraction layer now?

Discovery produces **analysis and recommendation only**.

---

## Product

Use Product when a request is a **feature idea or vague requirement**.

Product will:

- clarify scope
- define non-goals
- write acceptance criteria
- break work into tasks

Typical requests:

- Define the MVP for export
- Break this feature into tasks
- Write a specification for translation settings

Product produces **specifications and tasks**, not code.

---

## Architect

Use Architect when a **task already exists** and needs an implementation plan.

Architect will:

- restate the task
- define an implementation plan
- define acceptance criteria
- list files that will change
- identify dependencies and risks
- ensure the plan respects architecture guardrails

Architect produces **an implementation plan**, not code.

---

## Builder

Use Builder when there is **an approved Architect plan**.

Builder will:

- implement the plan step-by-step
- modify the smallest possible number of files
- run verification steps
- avoid expanding scope

Builder must **not start without an Architect plan**, except for trivial fixes.

---

## Reviewer

Use Reviewer after Builder finishes implementation.

Reviewer checks:

- scope compliance
- architecture alignment
- tests
- safety
- dependency usage

Reviewer must **not implement features**.

---

# Standard Development Flow

Typical feature development:

```
Discovery (optional)
↓
Product (optional)
↓
Architect
↓
Builder
↓
Reviewer
```

Rules:

- Never start with Builder unless a concrete implementation step exists
- Never skip Reviewer for code changes
- Use Discovery or Product only when necessary

---

# Using the Prompt Templates

Each file in this directory contains a prompt template.

Typical usage:

1. Copy the prompt template
2. Insert the task or feature request
3. Run the prompt

Example:

```
Read:
- AGENTS.md
- agents/architect.md
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/TASKS.md
- docs/DECISIONS.md

Act as the Architect agent.

Do not write code.

Task:
<PASTE TASK HERE>

Produce the output exactly in the format defined in agents/architect.md.
```

---

# Key Rules

Agents must:

- follow the architecture in `docs/ARCHITECTURE.md`
- respect the constraints defined in `docs/ARCHITECTURE_GUARDRAILS.md`
- keep changes small and reviewable
- avoid unnecessary dependencies
- record significant decisions in `docs/DECISIONS.md`
- update documentation when required
- use `docs/ARCHITECTURE_CHECKLIST.md` for non-trivial architectural reviews

If uncertain:

→ choose the **simplest working solution**.