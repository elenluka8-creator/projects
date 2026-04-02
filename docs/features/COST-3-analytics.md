# Analytics Specification — COST-3: Express Tier Visibility

**Feature:** COST-3 — Express tier visibility in upload UI
**Prepared for:** Architect and Builder
**Related tasks:** COST-3-T1, COST-3-T2
**Date:** 2026-03-28

---

## Analytics Goal

Measure whether changing the default quality tier from Standard to Express increases Express adoption and reduces unnecessary credit consumption per job. The primary questions are: (1) what percentage of submitted jobs use the Express tier after this change, and (2) how frequently do users deviate from the Express default to choose a different tier. Both questions are answerable from data that is already captured at job submission — no new instrumentation is required for COST-3.

---

## Events

### Existing event: job_submitted (via `api.submitJob`)

**Pipeline stage:** ingestion (job creation / frontend submission)
**Trigger:** User submits the upload form; `api.submitJob()` is called with the full job configuration.
**Status:** Already instrumented. `quality_tier` is already included in `SubmitJobRequest` and is stored in the backend job record (evidenced by `AdminJobRow.quality_tier`). No new event definition is required.

**Relevant properties already present:**
- `quality_tier`: string — the tier submitted with the job (`"express"`, `"standard"`, `"premium"`)
- `mode`: string — `"translate"` or `"guided"`
- `target_language`: string
- `word_count_estimate`: int (optional)
- `credit_estimate`: int

**Conclusion:** `job_submitted` already captures `quality_tier`. It is sufficient for all product metrics defined in this specification. No redundant event should be added.

---

### Candidate event: tier_selected

**Trigger:** User explicitly clicks a tier `ModeCard` in the tier fieldset, changing `qualityTier` state away from the current value.
**Instrumentation location:** `onSelect` callback on each `ModeCard` inside the QUALITY_TIERS fieldset in `web/app/[locale]/upload/page.tsx`.
**Status:** Optional. Cannot be implemented without a frontend analytics library. No such library exists in the codebase at the time of this specification. This event is deferred; if a frontend analytics library is introduced in a future task, `tier_selected` should be instrumented then.

---

### Candidate event: tier_badge_seen

**Trigger:** Express tier card with the "Recommended" badge enters the user's viewport.
**Status:** Not feasible. Impression tracking requires an IntersectionObserver integration wired to a frontend analytics sink. Neither exists in the current codebase. Do not implement.

---

## Event Schema

No new event schema is required. The job record already contains `quality_tier` as a stored field on every submitted job. Analytics are derived from the existing job table.

For reference, the existing submission payload that already includes the tier:

```json
{
  "mode": "string",
  "target_language": "string",
  "source_language_override": "string | null",
  "translation_style": "string",
  "user_level": "string",
  "explanation_depth": "string",
  "source_artifact_id": "string",
  "word_count_estimate": "int | null",
  "credit_estimate": "int",
  "quality_tier": "string",
  "ui_locale": "string | null"
}
```

All fields are passed to the backend and stored. `quality_tier` is non-nullable in practice (defaults to `"express"` after COST-3).

---

## Metrics

### Product metrics

- **express_tier_adoption_rate**
  Definition: `count(jobs where quality_tier = "express") / count(all jobs)`
  Source: job table (`quality_tier` column)
  Notes: Baseline should be captured before COST-3 ships. Compare post-COST-3 rate to baseline to measure impact.

- **tier_deviation_rate**
  Definition: `count(jobs where quality_tier != "express") / count(all jobs)`
  Source: job table (`quality_tier` column)
  Notes: After COST-3, Express is the default. Any non-Express submission indicates a deliberate tier change by the user. A high deviation rate may signal that users prefer Standard or Premium despite the new default.

### Quality metrics

- **express_credit_efficiency**
  Definition: `avg(credit_estimate) for jobs where quality_tier = "express"` vs `avg(credit_estimate) for jobs where quality_tier = "standard"`
  Source: job table (`credit_estimate`, `quality_tier` columns)
  Notes: Validates that Express jobs consume fewer credits per job on average, confirming the cost-reduction goal is achieved in practice.

### Operational metrics

No new operational metrics. The tier change is a UI-only default modification with no pipeline or infrastructure impact.

---

## Instrumentation Requirements

Builder must:

- **Make no changes to analytics instrumentation.** The `quality_tier` field is already included in `api.submitJob()` calls (line 525 of `web/app/[locale]/upload/page.tsx`) and is already stored by the backend. COST-3 changes only the default value passed (`"express"` instead of `"standard"`); the instrumentation remains valid without modification.
- **Do not add `tier_selected` or `tier_badge_seen` events.** No frontend analytics library exists. Adding event calls without a working sink would produce dead code.
- **Do not add any backend changes** beyond what the COST-3 feature specification permits.

---

## Validation Rules

Analytics Validator must verify:

- `quality_tier` is present and non-null in the `SubmitJobRequest` payload for all submitted jobs.
- The default value of `qualityTier` state in `web/app/[locale]/upload/page.tsx` is `"express"` (not `"standard"`).
- No new frontend analytics event calls (`analytics.track`, `logEvent`, or equivalent) were added — these would require a library that does not exist and must not be introduced as dead code.
- The `quality_tier` value submitted matches the tier the user selected in the UI (i.e., no hardcoded override is present in `handleSubmit`).
- No PII fields have been added to any submission payload as part of COST-3.

---

## Assumptions Made

- `AdminJobRow.quality_tier` already exists as a stored column in the backend job table. This is confirmed by its presence in the `AdminJobRow` interface in `web/lib/api.ts`. Metric queries can be run against this column without schema changes.
- No frontend analytics library (e.g., Segment, PostHog, Mixpanel, custom) is present in the codebase. This was confirmed by inspection of `web/app/[locale]/upload/page.tsx` and `web/lib/api.ts` — no analytics import or event call exists.
- After COST-3, the `express` tier becomes the new default. Any pre-COST-3 baseline for `express_tier_adoption_rate` should be captured from existing job data before the feature ships.
- `tier_selected` and `tier_badge_seen` are deferred, not cancelled. If a frontend analytics library is introduced later, these events should be revisited.
