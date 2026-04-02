# FIX-5 — Cache Token Ledger: Implementation Plan

## Task Restatement

Pass `cache_creation_tokens` and `cache_read_tokens` from `BatchResult` through to `record_batch_cost` so that the cost ledger uses the correct Anthropic cache-aware formula instead of overestimating spend whenever prompt caching fires.

---

## Plan

### Step 1 — `models.py`: Add cache token fields to `BatchResult` [small]

Add two optional integer fields with `default=0` to the `BatchResult` dataclass:

```python
cache_creation_tokens: int = 0
cache_read_tokens: int = 0
```

Both fields default to `0` so all existing construction sites (tests, stub providers, `_StubProvider` in `test_pipeline_translation.py`) remain valid without any edits.

### Step 2 — `provider.py`: Populate `BatchResult` cache fields [small]

In `AnthropicProvider.translate_batch`, the 6-tuple from `_call_api` is already unpacked as:

```python
raw, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms = self._call_api(...)
```

The `BatchResult` construction below that unpack currently omits the cache fields. Change it to:

```python
return BatchResult(
    translated_segments=translated,
    tokens_in=tokens_in,
    tokens_out=tokens_out,
    cache_creation_tokens=cache_creation_tokens,
    cache_read_tokens=cache_read_tokens,
    new_terms=consistency_updates,
    new_entities=new_entities,
    chapter_summary=chapter_summary,
    latency_ms=latency_ms,
)
```

No other changes to `provider.py`. `TranslationProviderProtocol.translate_batch` signature is unchanged.

### Step 3 — `estimator.py`: Add `usd_per_1k_cache_read_tokens` field to `EstimationConfig` [small]

Add a new field to the frozen `EstimationConfig` dataclass and wire it to `from_env()`:

```python
usd_per_1k_cache_read_tokens: Decimal  # new field
```

In `from_env()`:

```python
usd_per_1k_cache_read_tokens=Decimal(
    os.getenv("COST_USD_PER_1K_CACHE_READ_TOKENS", "0.0003")
),
```

**Naming rationale:** The existing env vars follow the pattern `COST_USD_PER_1K_TOKENS_IN` / `COST_USD_PER_1K_TOKENS_OUT`. The new name `COST_USD_PER_1K_CACHE_READ_TOKENS` follows the same convention and is self-documenting.

**Default value:** `0.0003` — Anthropic's cache read price ($0.30/1M = $0.0003/1K), which is 10% of the standard input price (`0.003/1K` at list; note the codebase currently defaults `COST_USD_PER_1K_TOKENS_IN` to `0.0015`, which is the haiku rate — the 10% ratio holds regardless of the absolute rate).

`cache_creation_tokens` cost at the same rate as normal input tokens per Anthropic pricing, so no separate constant is needed for them.

### Step 4 — `ledger.py`: Update `_calculate_cost_usd` and `record_batch_cost` [small]

**Update `_calculate_cost_usd`:**

Add a `cache_read_tokens: int = 0` parameter. Apply the cache-aware formula:

```
billable_tokens_in = tokens_in - cache_read_tokens
cost_in     = (billable_tokens_in / 1000) × usd_per_1k_tokens_in
cost_cache  = (cache_read_tokens  / 1000) × usd_per_1k_cache_read_tokens
cost_out    = (tokens_out         / 1000) × usd_per_1k_tokens_out
total       = cost_in + cost_cache + cost_out
```

`cache_creation_tokens` are billed at the normal input rate and are already included in `tokens_in` as reported by the Anthropic API, so no separate term is needed.

**Update `record_batch_cost`:**

Add a keyword-only parameter `cache_read_tokens: int = 0` (default 0 preserves all existing call sites). Pass it through to `_calculate_cost_usd`. Also add it to the structured log payload.

Signature change:

```python
def record_batch_cost(
    session: Session,
    job_id: uuid.UUID,
    tokens_in: int,
    tokens_out: int,
    estimation_config: EstimationConfig | None = None,
    *,
    cache_read_tokens: int = 0,          # new
    job_run_id: Optional[uuid.UUID] = None,
    batch_index: Optional[int] = None,
    provider: Optional[str] = None,
) -> CostLedgerEntry:
```

### Step 5 — `orchestrator.py`: Pass `cache_read_tokens` in `_on_batch_complete` [small]

In `_on_batch_complete`, the call to `record_batch_cost` currently passes only `tokens_in` and `tokens_out`. Add `cache_read_tokens`:

```python
record_batch_cost(
    session=session,
    job_id=job.job_id,
    tokens_in=result.tokens_in,
    tokens_out=result.tokens_out,
    cache_read_tokens=result.cache_read_tokens,   # new
    job_run_id=run.job_run_id,
    batch_index=batch_index,
    provider="anthropic",
)
```

The preamble call in `_on_preamble_complete` does not need updating — `PreambleResult` does not carry cache tokens and preamble calls do not use the cached system prompt.

---

## Acceptance Criteria

- `BatchResult` has `cache_creation_tokens: int = 0` and `cache_read_tokens: int = 0`; existing code constructing `BatchResult` without these fields compiles and passes tests without modification.
- `AnthropicProvider.translate_batch` populates both cache fields from the `_call_api` 6-tuple.
- `EstimationConfig` has `usd_per_1k_cache_read_tokens` with default `0.0003`; `COST_USD_PER_1K_CACHE_READ_TOKENS` env var overrides it.
- `_calculate_cost_usd` with `cache_read_tokens > 0` produces a cost strictly lower than the same call with `cache_read_tokens = 0` (discount is applied).
- `record_batch_cost` accepts `cache_read_tokens` as a keyword arg (default `0`); existing callers are unaffected.
- `_on_batch_complete` in `orchestrator.py` passes `result.cache_read_tokens` to `record_batch_cost`.
- All existing tests pass unchanged.

---

## Non-goals

- Updating `CostLedgerEntry` DB schema to persist `cache_read_tokens` as a column (the formula change is sufficient for correct cost recording; schema changes require a migration and are out of scope for this fix).
- Correcting the pre-admission `estimate_job_cost` function — it estimates cost before caching is known and intentionally ignores it.
- Adding `cache_read_tokens` to `TranslationBatch` DB records.
- Updating the preamble cost path in `_on_preamble_complete`.

---

## Dependencies

- **external:** none
- **internal:** `app.cost.estimator.EstimationConfig` (step 3 must land before step 4 to avoid import errors during Builder implementation)

---

## Files

| Action | Path | Reason |
|--------|------|--------|
| modify | `app/pipeline/translation/models.py` | Add `cache_creation_tokens` and `cache_read_tokens` fields to `BatchResult` |
| modify | `app/pipeline/translation/provider.py` | Populate new `BatchResult` fields from `_call_api` return tuple |
| modify | `app/cost/estimator.py` | Add `usd_per_1k_cache_read_tokens` to `EstimationConfig` |
| modify | `app/cost/ledger.py` | Update `_calculate_cost_usd` and `record_batch_cost` to use cache-aware formula |
| modify | `app/worker/orchestrator.py` | Pass `cache_read_tokens` to `record_batch_cost` in `_on_batch_complete` |
| modify | `tests/test_cost_ledger.py` | Update `_CONFIG` fixture and add cache-read cost tests |
| modify | `tests/test_cost_estimator.py` | Update `_CONFIG` construction to include new `usd_per_1k_cache_read_tokens` field |
| modify | `tests/test_pipeline_translation.py` | Update `_CONFIG`-equivalent and add a test asserting `BatchResult.cache_read_tokens` is populated from provider |

---

## Risks

- **`EstimationConfig` is a frozen dataclass.** Any call site constructing `EstimationConfig(...)` with positional arguments will break silently on the wrong field order if the new field is inserted in the wrong position. Mitigation: add `usd_per_1k_cache_read_tokens` as the last field so no positional call sites are affected by reordering.
- **Test fixtures construct `EstimationConfig` directly.** Two test files (`test_cost_ledger.py`, `test_cost_estimator.py`) hard-construct `_CONFIG`. Both will fail with a `TypeError` until updated to include the new field. These are the only two affected test files (confirmed by grep: no other test files call `record_batch_cost` or instantiate `EstimationConfig`).
- **`tokens_in` reported by Anthropic includes `cache_read_tokens`.** The formula `billable_tokens_in = tokens_in - cache_read_tokens` relies on this. Confirmed by Anthropic API documentation: `input_tokens` in `usage` includes cache read tokens. If this behaviour changes upstream, the formula would under-count. No mitigation needed now; flag for future monitoring.

---

## Architectural Notes

- No pipeline boundary changes. All modifications are within existing modules.
- No new external dependencies.
- The `TranslationProviderProtocol` interface is unchanged; `BatchResult` is an internal type.
- `cache_creation_tokens` is carried through `BatchResult` for completeness (logging already uses it in `provider_batch_ok`) but does not alter the cost formula — Anthropic bills cache creation at standard input rates.

---

## Assumptions Made

- `tokens_in` in the Anthropic `usage` object already includes `cache_read_input_tokens` in its count (confirmed by Anthropic API behaviour: `input_tokens` = non-cached tokens read + cached tokens read). The formula therefore subtracts `cache_read_tokens` from `tokens_in` rather than treating them as an additive term.
- The `usd_per_1k_cache_read_tokens` default of `0.0003` is the correct Anthropic Haiku cache-read price and is intentionally expressed as a percentage of the input price, not hardcoded as a fraction of `usd_per_1k_tokens_in`, to keep both independently overridable via env vars.

---

## Smallest Next Step

Add `cache_creation_tokens: int = 0` and `cache_read_tokens: int = 0` to `BatchResult` in `app/pipeline/translation/models.py` — this is a safe, backward-compatible change with no downstream effects that unblocks all subsequent steps.

---

## Optional Follow-ups

- Add `cache_read_tokens` and `cache_creation_tokens` columns to `CostLedgerEntry` for per-batch audit visibility (requires a DB migration; low priority).
- Emit a `cost_cache_savings` analytics event so cache savings are observable in dashboards.
- Update `estimate_job_cost` to optionally accept an expected cache-hit ratio for more accurate upfront estimates on re-processed jobs.

---

```json
{
  "handoff": {
    "agent": "Architect",
    "artifact_type": "implementation_plan",
    "artifact_path": "docs/plans/FIX-5-cache-token-ledger.md",
    "status": "produced",
    "next_recommended_agent": "Spec Reviewer",
    "next_recommended_reason": "Implementation plan produced; quality loop recommended before Builder begins.",
    "blocking_issues": [],
    "workflow_state": {
      "task_id": "FIX-5",
      "artifact_id": "ARCH-FIX-5",
      "current_stage": "architecture",
      "quality_loop_iteration": 0,
      "builder_cycle_count": 0,
      "analytics_used": false,
      "product_spec_accepted": false
    }
  }
}
```
