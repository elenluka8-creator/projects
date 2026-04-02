# Code Audit — 2026-03-28

Auditor: Senior code review pass against recently changed files and known problem areas.
Scope: `app/pipeline/translation/`, `app/worker/`, `app/notifications/`, `app/cost/`, `app/db/models/`, `app/api/routers/jobs.py`, `alembic/versions/`, `web/app/[locale]/upload/page.tsx`.

---

## Critical issues

None found.

---

## High severity issues

### H-1 — `BatchResult` drops `cache_creation_tokens` / `cache_read_tokens`; cost ledger overcharges for cached calls

**Files:**
- `app/pipeline/translation/models.py` lines 68–81 (`BatchResult`)
- `app/pipeline/translation/provider.py` lines 226–265 (`translate_batch`)
- `app/worker/orchestrator.py` lines 597–605 (`_on_batch_complete`)
- `app/cost/ledger.py` lines 28–74 (`record_batch_cost`)

**Description:**
`_call_api` returns a 6-tuple `(text, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms)`. Inside `translate_batch`, `cache_creation_tokens` and `cache_read_tokens` are correctly extracted from the tuple and logged in `provider_batch_ok`. However, `BatchResult` has no fields for these values, so they are silently dropped before the result reaches the orchestrator.

`record_batch_cost` is then called with only `tokens_in` and `tokens_out`, treating all input tokens as uncached. Anthropic prices cached reads at ~10% of uncached input token cost. With prompt caching active (system prompt uses `cache_control: ephemeral`), every batch after the first will have most of its input tokens cached. The cost ledger will overestimate real API spend, and if cost ledger entries feed any user-facing credit deduction logic the user would be over-debited.

**Suggested fix:**
1. Add `cache_creation_tokens: int = 0` and `cache_read_tokens: int = 0` to `BatchResult`.
2. Propagate the values from the 6-tuple unpack in `translate_batch`.
3. Add matching parameters to `record_batch_cost` and store them in `CostLedgerEntry` (requires a migration).
4. Adjust `_calculate_cost_usd` to charge cache reads at the correct rate.

---

### H-2 — Duplicate `TranslationBatch` rows on re-run when S3 artifact is missing

**File:** `app/worker/orchestrator.py` lines 426–476 (`_run_translate`)  
**File:** `app/worker/orchestrator.py` lines 576–619 (`_on_batch_complete`)  
**File:** `alembic/versions/0008_create_translation_batches.py`

**Description:**
`_run_translate` has a resumability guard: if `total_batches_in_db > 0` and all batches show `status = 'completed'`, it tries to load the serialized artifact from S3. If S3 loading fails (artifact was never saved, was deleted, or storage is temporarily unavailable), the code logs a warning and **falls through to a full re-run** — calling `run_translation(...)` again from scratch.

`_on_batch_complete` creates a new `TranslationBatch` row for each batch (lines 585–595). There is no check for an existing row with the same `(job_run_id, batch_index)`, and there is **no unique constraint** on that pair in migration 0008 or in the ORM model. After the re-run, `total_batches_in_db` doubles. The resumability check `len(completed_batch_indices) >= total_batches_in_db` will never fire for the doubled count, meaning a third crash would result in a triple-run. Cost ledger also gets duplicate entries.

**Suggested fix (choose one):**
- **Option A (preferred):** Add a `UniqueConstraint("job_run_id", "batch_index")` to `TranslationBatch` and a corresponding migration. The re-run will raise an integrity error that propagates as a system failure and is logged.
- **Option B:** Before falling through to a full re-run, delete all existing `TranslationBatch` rows for `job_run_id` from the DB, then proceed with the re-run.
- **Option C:** Use an upsert / `INSERT … ON CONFLICT DO UPDATE` pattern in `_on_batch_complete`.

---

## Medium severity issues

### M-1 — Watchdog enqueues before committing; Redis and DB can diverge on commit failure

**File:** `app/worker/run.py` lines 51–69 (`_run_watchdog`) and lines 114–130 (startup recovery)

**Description:**
The watchdog modifies `run.status`, `run.worker_id`, and `run.lease_expires_at`, then calls `broker.enqueue(run.job_run_id)` — all inside the loop — before the single `session.commit()` at line 69. If the commit fails (DB error, connection drop), the session is rolled back and the DB still shows the run as `"leased"` or `"processing"`. But the IDs are already in the Redis queue.

When the worker dequeues them, `acquire_lease` returns `False` (run.status ≠ `"created"`). The re-enqueue guard in `process_one` also checks for `"created"` status (line 161), so the run is silently discarded. The run will remain stuck until the next watchdog pass re-detects it.

The same pattern appears in the startup recovery block at lines 114–130.

**Suggested fix:** Commit status changes before enqueuing, or commit per orphan inside the loop rather than once at the end. A single atomic commit per orphan is safest.

---

### M-2 — `_run_translate` progress uses planning estimate for `total_batches`, not actual count

**File:** `app/worker/orchestrator.py` lines 531–533, 617

**Description:**
```python
total_batches = max(1, n_hints, est)
```
`total_batches` is derived from batch-planning estimates (`n_hints`, `est`) before translation begins. This value is used in `_on_batch_complete` at line 617:
```python
percent=translate_progress_percent(batch_index, total_batches),
```
If the actual number of translation batches differs from the estimate (e.g., cross-chapter merging changed the count), `translate_progress_percent` can return values > 100% for later batches, and the job may display 100% before all batches are done, or stall below 100%.

**Suggested fix:** Track the actual batch count as batches are created (increment a counter in `_on_batch_complete`), or read `total_batches_in_db` after translation completes to set `progress_percent = 100` at the right moment. At minimum, clamp `translate_progress_percent` output to [0, 99] during in-progress updates.

---

### M-3 — `SubmitJobRequest` lacks enum validation for key fields

**File:** `app/api/routers/jobs.py` lines 66–78

**Description:**
`SubmitJobRequest` accepts `mode`, `quality_tier`, `translation_style`, `user_level`, and `explanation_depth` as unconstrained `str`. While `job_service.submit_job` validates these downstream, there is no Pydantic-layer enforcement. A malformed request reaches the service layer unnecessarily and generates a 422 from there rather than from the schema. This also means OpenAPI docs don't enumerate valid values.

**Suggested fix:** Use `Literal` types or `Enum`:
```python
from typing import Literal
mode: Literal["translate", "guided"]
quality_tier: Literal["express", "standard", "premium"] = "standard"
translation_style: Literal["literal", "natural"] = "natural"
user_level: Literal["A1", "A2", "B1", "B2", "C1"] = "B1"
explanation_depth: Literal["minimal", "standard", "detailed"] = "standard"
```

Note: The `quality_tier` default in `SubmitJobRequest` is `"standard"` (line 73) while the frontend defaults to `"express"`. The frontend always sends the field explicitly so there is no mismatch in practice, but the inconsistency should be documented or aligned.

---

### M-4 — `Jinja2(autoescape=False)` in notification service is an HTML-safety latent risk

**File:** `app/notifications/notification_service.py` line 46

**Description:**
Templates are currently plain-text (`.txt.j2`) and contain user-controlled values `display_name` and `book_title`. `autoescape=False` is correct for plain text. However, if templates are ever switched to HTML without updating this setting, `display_name` or `book_title` could inject HTML/script content into the email body.

**Suggested fix:** Add an explicit comment noting the assumption, or pre-escape user-controlled variables regardless, or switch to `autoescape=True` and use `| safe` in templates where literal markup is needed.

---

## Low severity issues / code quality

### L-1 — `except Exception: pass` in analytics block logs nothing

**File:** `app/api/routers/jobs.py` lines 240–241

```python
except Exception:
    pass  # analytics must not block submission
```
The intent is correct, but a bare `pass` means analytics failures are completely invisible. Any misconfiguration or bug in the logging path is silently swallowed.

**Suggested fix:** Log a warning with `exc_info=True`:
```python
except Exception:
    log_structured(logger, logging.WARNING, "analytics_event_failed", {}, exc_info=True)
```

---

### L-2 — `except Exception: pass` in JSON repair fallback hides import errors

**File:** `app/pipeline/translation/provider.py` lines 441–453

The `except Exception: pass` after `from json_repair import repair_json` means an `ImportError` (package not installed) is silently swallowed and the function raises `_JsonParseError` with no indication that repair was unavailable. In a deployment without `json-repair` installed, every JSON parse failure would fail silently rather than retrying or alerting.

**Suggested fix:** Log the exception before passing, or catch `ImportError` separately and log a warning.

---

### L-3 — Redundant `import os` inside `_call_api`

**File:** `app/pipeline/translation/provider.py` line 386

`os` is already imported at the module top (line 17). The repeated `import os` inside `_call_api` is harmless (Python caches modules) but is misleading.

**Suggested fix:** Remove the inner `import os`.

---

### L-4 — `_on_batch_complete` passes `cache_creation_tokens` / `cache_read_tokens` to log but `BatchResult` has no such fields

(Related to H-1. Listed separately for the code review record.)

The log payload in `provider_batch_ok` (lines 248–250 of `provider.py`) correctly captures these values from the `_call_api` 6-tuple. But since `BatchResult` drops them, any consumer of `BatchResult` (including tests) cannot access them. This makes the cache metrics effectively write-only — logged but unactionable.

---

### L-5 — `release_lease` does not reset `run.status`; run stays in `"processing"` after release

**File:** `app/worker/lease.py` lines 79–90

```python
def release_lease(session, job_run_id, worker_id):
    run.worker_id = None
    run.lease_expires_at = None
    session.flush()
```

`run.status` is not reset on release. After a successful pipeline run, `_complete_job` sets `run.status = "completed"` and commits, so by the time `release_lease` is called in the `finally` block the status is correct. However, if `release_lease` is called after a partial failure where `_handle_failure` was not reached (e.g., `_execute_pipeline` raises before setting status), the run could be left with `status = "leased"` after the lease fields are cleared, which would confuse `detect_expired_leases` on the next watchdog pass (the query filters on `lease_expires_at != None`). In practice this is protected by the `except Exception as exc: self._handle_failure(...)` block in `process_one`, but the defense-in-depth is fragile.

---

### L-6 — `_LEASE_DURATION_SECONDS` and `_normalize_aware` lack blank-line separation

**File:** `app/worker/orchestrator.py` lines 97–101

Minor formatting: the constant and the helper function are adjacent without a blank line separator, making the file harder to scan.

---

### L-7 — `user.email` emptiness not validated before notification dispatch

**File:** `app/worker/orchestrator.py` line 968; `app/db/models/user.py` line 27

`User.email` is `nullable=False` so it cannot be `None` in the DB. However, an empty-string `""` is not excluded. `send_email(to="", ...)` would call the Resend API with an invalid `to` field; the error is caught and logged as `email_send_failed`. No crash, but a confusing log line.

**Suggested fix:** Add a guard before calling `send_job_completion_notification`:
```python
if user is not None and user.email:
    ...
```

---

## No issues found in

- `app/pipeline/translation/preamble.py` — 6-tuple is now correctly unpacked (`raw, tokens_in, tokens_out, _cache_creation, _cache_read, latency_ms`). Graceful-degradation pattern is solid.
- `app/worker/lease.py` — `acquire_lease`, `renew_lease`, `detect_expired_leases`, `find_unqueued_created_runs` are all correct and safe.
- `app/worker/run.py` — Worker loop, signal handling, and watchdog thread are structured correctly. Startup recovery logic is sound. (M-1 above is about commit ordering inside the watchdog, not the overall structure.)
- `app/notifications/email_client.py` — Thin, defensive, never raises. Non-fatal design is respected.
- `app/notifications/notification_service.py` — Locale fallback, template rendering, and exception handling are all correct.
- `app/cost/estimator.py` — Decimal arithmetic is correct. `CostCapConfig` and `EstimationConfig` are cleanly env-sourced.
- `app/cost/ledger.py` — `record_batch_cost` is correct for the token inputs it receives. (H-1 is about what inputs it should receive, not internal logic.)
- `app/db/models/job.py` — `ui_locale: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)` is present and covered by migration 0017.
- `app/db/models/artifact.py` — `"translation_collection"` is in `ARTIFACT_TYPES` frozenset (line 19). Artifacts table stores `artifact_type` as a plain `String` (no DB enum), so any value in `ARTIFACT_TYPES` is valid. Migration 0003 is aligned.
- `alembic/versions/0015` through `0017` — All migrations are syntactically correct and consistent with model definitions.
- `app/pipeline/translation/provider.py` — Return type consistency: the 6-tuple is returned correctly in all paths. No callers outside `preamble.py` and `translate_batch` call `_call_api` directly.
- **Frontend `web/app/[locale]/upload/page.tsx`** — Credit estimate IS correctly recalculated on page load after upload: `useEffect` at line 507–510 depends on `phase.name`, `qualityTier`, `mode`, and all other config fields. When `phase` transitions to `"done"`, `fetchEstimate` is called with the current `qualityTier` (which defaults to `"express"`). No stale estimate issue.

---

## Summary and recommended actions

| Priority | Item | Action |
|----------|------|--------|
| **H-1** | Cache token cost tracking | Add `cache_creation_tokens` / `cache_read_tokens` to `BatchResult`, propagate to `record_batch_cost`, store in `CostLedgerEntry`, adjust cost formula |
| **H-2** | Duplicate `TranslationBatch` rows | Add `UniqueConstraint("job_run_id", "batch_index")` migration or upsert logic in `_on_batch_complete` |
| **M-1** | Watchdog commit-before-enqueue | Commit per orphan before enqueueing its ID |
| **M-2** | Progress `total_batches` accuracy | Track actual batch count; clamp progress ≤ 99 during in-progress updates |
| **M-3** | Pydantic enum validation on `SubmitJobRequest` | Use `Literal` types for `mode`, `quality_tier`, `translation_style`, `user_level`, `explanation_depth` |
| **M-4** | Jinja2 autoescape comment | Add comment; no immediate code change required |
| **L-1** | Silent analytics exception | Add `exc_info=True` warning log |
| **L-2** | Silent JSON repair import failure | Log exception before passing |
| **L-3** | Redundant `import os` | Remove inner import |
| **L-7** | Empty email guard | Add `if user.email:` guard before notification call |

**Highest impact items in order:** H-1 (cost correctness), H-2 (data integrity on resume), M-1 (reliability on DB transient failure), M-3 (API hardening).

H-1 and H-2 should be tracked as new tasks in `docs/TASKS.md` and go through the full Architect → Builder → Reviewer cycle before shipping to production.
