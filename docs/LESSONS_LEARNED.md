# Lessons learned

Project-specific log of what went wrong in completed workflows, what review feedback repeated, and what worked. **Append-only** by default — do not delete history; Iteration Manager may add a short “superseded by” note if a lesson no longer applies.

**Maintainer:** Iteration Manager appends a new section after each workflow that reached completion (Reviewer approved) or was explicitly closed with a documented outcome.

**Audience:** Every agent reads this file (with `KNOWN_PATTERNS.md`) before starting work, per `AGENTS.md`.

---

## How to write an entry

Use one block per closed workflow. Keep it factual and short.

```markdown
## YYYY-MM-DD — <task id or short title>

**Workflow outcome:** completed | closed (other)

### What went wrong
- ...

### Repeated must_fix / review / security themes
- ... (quote or paraphrase recurring themes from Spec Reviewer, Reviewer, Security Reviewer)

### What worked well
- ... (optional; durable wins also belong in `KNOWN_PATTERNS.md`)

### Follow-ups
- ... (optional — links to `docs/TASKS.md` entries if any)
```

---

## Entries

*(Iteration Manager appends below this line.)*

## 2026-03-29 — FIX-9: Worker restart leaves processing runs stuck

**Workflow outcome:** completed

### What went wrong
- `acquire_lease()` only accepts `status='created'`. When a worker is killed mid-job (Railway redeploy), the run stays in `processing` with an active 8-hour lease. The new worker cannot acquire it; the watchdog ignores it until the lease expires.
- The first FIX-9 commit reset the run's status but did not delete partial `translation_batches`. On restart the worker tried to INSERT `batch_index=0` again → unique constraint violation.
- A second commit added the batch DELETE to startup recovery. This combination fixed the issue.
- Root trigger: agent framework sync commits (`v1.0.1`, `v1.0.2`, `v1.0.3`) pushed while a long job was running, causing three back-to-back redeploys that each killed the worker mid-translation.

### Repeated must_fix / review / security themes
- Startup recovery must cover ALL stuck statuses, not just expired leases.
- Partial state cleanup (DB rows tied to a run being reset) must happen atomically with the status reset — otherwise the next attempt hits a constraint violation.

### What worked well
- Adding `find_active_processing_runs()` as a complement to `detect_expired_leases()` was clean and non-overlapping.
- Deleting `translation_batches` (but preserving `job_consistency_snapshots`) gave a clean restart without losing accumulated terminology/entity memory.

### Follow-ups
- FIX-3 (per-batch skip on partial resume) — would avoid re-translating completed batches on each redeploy. Not blocking, but reduces wasted cost.
