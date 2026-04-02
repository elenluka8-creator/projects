# COST-1 Review — Anthropic Prompt Caching

**Date:** 2026-03-28  
**Reviewer:** Reviewer agent  
**Task:** COST-1 — Anthropic Prompt Caching for Static System Prompt  
**Plan:** `docs/plans/COST-1-prompt-caching.md`

---

## Review Result

**Status: APPROVED WITH MINOR CHANGES**

---

## Scope Check

Implementation follows the approved scope exactly. All five plan steps are addressed:

- **Step 1** — `system` kwarg changed from plain string to list with `cache_control` block. ✓
- **Step 2** — `cache_creation_input_tokens` and `cache_read_input_tokens` extracted with `getattr` fallbacks. ✓
- **Step 3** — Return value extended from 4-tuple to 6-tuple. ✓
- **Step 4** — `translate_batch` unpack and `provider_batch_ok` log payload updated. ✓
- **Step 5** — `TestAnthropicProviderCaching` class with 4 tests added. ✓

Only the two approved files were modified: `app/pipeline/translation/provider.py` and `tests/test_pipeline_translation.py`. No other files were touched.

No unrelated refactoring, no renamed symbols, no moved modules. Scope is clean.

---

## Architecture Check

No architecture concerns. The change is entirely within the LLM integration boundary defined by DEC-003 — only `provider.py` imports or calls the Anthropic client. No pipeline stage boundary is crossed. No stage contract changes. No hidden cross-stage coupling introduced.

`TranslationProviderProtocol`, `BatchResult`, and `translate_batch` signatures are all unchanged. The change is internal to `_call_api`, a private method with no external callers.

Guardrail Rule 6 (hidden caching that alters behavior) is not violated: Anthropic-side prompt caching is read-only and does not alter model output. It affects cost, not pipeline behavior.

---

## Prompt Integrity

Prompt templates were not modified. No `prompts/` directory changes. `_call_api` receives `system` as a plain string from `prompt_template.system` (loaded from YAML) and wraps it in the list format internally. The prompt content is unchanged.

---

## AI / LLM Check

- Model name is not hardcoded. `self._model` is sourced from `TRANSLATION_MODEL` env var, falling back to `_DEFAULT_MODEL` constant. ✓
- No new models or providers introduced. ✓
- Token usage logging in `provider_batch_ok` is preserved. Cache token fields (`cache_creation_tokens`, `cache_read_tokens`) are added to the log at INFO level. ✓
- Temperature and determinism settings are unchanged. ✓

---

## Code Quality

The implementation is minimal and clear. Changes are surgical:

- Lines 391–394 in `_call_api`: `system` list construction is explicit and readable.
- Lines 412–413: `getattr(..., 0) or 0` double-safety pattern (handles both missing attribute and `None` return) matches the plan exactly.
- Lines 226–229: 6-value unpack in `translate_batch` is clear and matches the return tuple.
- Lines 244–255: `provider_batch_ok` log payload extended with the two new fields, no structural changes.

One pre-existing minor issue (not introduced by COST-1): `import os` appears redundantly inside `_call_api` at line 386, where `os` is already imported at module level on line 17. This is a pre-existing defect; COST-1 did not introduce it and did not need to fix it.

---

## Dependencies

No new dependencies introduced. The change uses the existing `anthropic` SDK already pinned at `>=0.84,<1.0` in `requirements.txt`, which supports `cache_control` in the system param. ✓

---

## Tests

All four new tests in `TestAnthropicProviderCaching` pass. External I/O is mocked correctly via `patch.object(provider, "_get_client")`. Tests are deterministic.

**Test name divergence from plan (non-blocking):** The plan specified:
- `test_cache_creation_tokens_logged`
- `test_cache_read_tokens_logged`

The implementation uses:
- `test_cache_creation_tokens_flow_through`
- `test_cache_read_tokens_flow_through`

Coverage is identical. The name change is cosmetically different but carries no functional consequence.

**Pre-existing test failure (not caused by COST-1):**

`TestConsistencyMemory::test_context_string_bounded` fails with:

```
assert 2001 <= 1510
```

This failure is pre-existing and unrelated to COST-1. The test file was in a modified (but not COST-1-introduced) state. The `ConsistencyMemory.to_context_string()` truncation logic does not appear to be honoring its 1500-character bound. This must be tracked and fixed as a separate task; it is not a blocker for COST-1 approval.

**Test run summary:**
```
33 passed, 1 failed in 0.52s
1 failure: test_context_string_bounded (pre-existing, unrelated to COST-1)
All 4 TestAnthropicProviderCaching tests: PASSED
```

---

## Security

No security concerns. No secrets are logged. No sensitive input data is exposed in error messages. The `system` list format contains the prompt text, which is already passed to the Anthropic API. No new data exposure surfaces introduced.

---

## Required Changes

None. No blocking issues.

---

## Suggested Improvements

- [optional] Track `test_context_string_bounded` failure as a separate task. The `ConsistencyMemory.to_context_string()` method is producing output of 2001 characters against a 1500-character bound. This regression (or pre-existing defect) is unrelated to COST-1 but should not remain unaddressed. Iteration Manager should create a follow-up task.
- [optional] Remove the redundant `import os` inside `_call_api` (line 386). Module-level import on line 17 already covers it. Minor cleanliness issue; no functional impact.

---

## Next Step

Iteration Manager marks COST-1 as `approved` and creates one follow-up task to investigate and fix the pre-existing `test_context_string_bounded` failure in `ConsistencyMemory`.

---

```json
{
  "handoff": {
    "agent": "Reviewer",
    "artifact_type": "code",
    "artifact_path": [
      "app/pipeline/translation/provider.py",
      "tests/test_pipeline_translation.py"
    ],
    "status": "approved",
    "next_recommended_agent": null,
    "next_recommended_reason": null,
    "blocking_issues": [],
    "workflow_state": {
      "task_id": "COST-1",
      "artifact_id": null,
      "current_stage": "validation",
      "quality_loop_iteration": 0,
      "builder_cycle_count": 0,
      "analytics_used": false,
      "product_spec_accepted": false
    }
  }
}
```
