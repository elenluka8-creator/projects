# COST-1 — Anthropic Prompt Caching for Static System Prompt

**Status:** ready for builder  
**Date:** 2026-03-28  
**Author:** Architect

---

## Task Restatement

Add Anthropic prompt caching (`cache_control` breakpoint) to the system prompt in `AnthropicProvider._call_api` so that the repeated ~2500-token system prompt is cached by Anthropic across all translation batches within a job, reducing input token billing.

---

## Plan

### Step 1 — Modify `_call_api` to send system prompt as a cacheable content block [small]

**File:** `app/pipeline/translation/provider.py`  
**Method:** `_call_api`

Change the `system` kwarg passed to `client.messages.create` from a plain string to a list containing a single content block with `cache_control`:

**Before:**
```python
kwargs = dict(
    model=self._model,
    max_tokens=MAX_TOKENS_RESPONSE,
    system=system,
    messages=[{"role": "user", "content": user}],
    timeout=...,
)
```

**After:**
```python
kwargs = dict(
    model=self._model,
    max_tokens=MAX_TOKENS_RESPONSE,
    system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": user}],
    timeout=...,
)
```

No other logic inside `_call_api` changes at this step.

---

### Step 2 — Extract cache token counts from `response.usage` [small]

**File:** `app/pipeline/translation/provider.py`  
**Method:** `_call_api`

After `response = client.messages.create(**kwargs)`, extract cache token counts using `getattr` with safe fallbacks (older SDK builds that pre-date caching do not expose these fields; `getattr` prevents `AttributeError`):

```python
usage = response.usage
tokens_in = usage.input_tokens
tokens_out = usage.output_tokens
cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
```

---

### Step 3 — Extend `_call_api` return value to carry cache metrics [small]

**File:** `app/pipeline/translation/provider.py`  
**Method:** `_call_api`

Change the return signature from a 4-tuple to a 6-tuple:

```python
return text, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms
```

`_call_api` is a private method (prefixed `_`). Only `translate_batch` calls it. No external callers exist.

---

### Step 4 — Update `translate_batch` to unpack and log cache metrics [small]

**File:** `app/pipeline/translation/provider.py`  
**Method:** `translate_batch`

Update the unpack line and the `provider_batch_ok` log payload:

```python
raw, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms = self._call_api(
    system=prompt_template.system,
    user=user_message,
)
```

Add cache fields to the existing `provider_batch_ok` structured log payload:

```python
log_structured(
    logger=logger,
    level=logging.INFO,
    message="provider_batch_ok",
    payload={
        "batch_index": batch_index,
        "segment_count": len(segments),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "latency_ms": round(latency_ms, 1),
        "model": self._model,
        "attempt": attempt,
    },
)
```

No change to `translate_batch` signature. No change to `BatchResult` construction. No change to `TranslationProviderProtocol`.

---

### Step 5 — Add unit tests for caching behaviour [small]

**File:** `tests/test_pipeline_translation.py`

Add a new test class `TestAnthropicProviderCaching` that mocks the Anthropic client directly (no real API calls). Tests must cover:

1. **`test_system_prompt_sent_with_cache_control`**  
   Assert that when `_call_api` is called, the `system` kwarg passed to `client.messages.create` is a list of length 1 containing `{"type": "text", "text": <system_text>, "cache_control": {"type": "ephemeral"}}`.

2. **`test_cache_creation_tokens_logged`**  
   Mock `response.usage` so that `cache_creation_input_tokens=512` and `cache_read_input_tokens=0`. Assert the return tuple includes `(512, 0)` in the cache token positions.

3. **`test_cache_read_tokens_logged`**  
   Mock `response.usage` so that `cache_creation_input_tokens=0` and `cache_read_input_tokens=2048`. Assert the return tuple includes `(0, 2048)` in the cache token positions.

4. **`test_cache_tokens_absent_from_usage_safe`**  
   Mock a `response.usage` object that has no `cache_creation_input_tokens` or `cache_read_input_tokens` attributes (simulating pre-caching SDK or non-cached response). Assert no `AttributeError` is raised and both cache token values default to `0`.

These tests use `unittest.mock.MagicMock` and `unittest.mock.patch` — both already imported in the test file. `AnthropicProvider` must be imported at the top of the test class (`from app.pipeline.translation.provider import AnthropicProvider`).

---

## Acceptance Criteria

- `client.messages.create` is always called with `system` as a list of content blocks, not a plain string.
- The content block has `cache_control: {"type": "ephemeral"}`.
- `provider_batch_ok` log events include `cache_creation_tokens` and `cache_read_tokens` fields.
- `translate_batch` signature is unchanged.
- `TranslationProviderProtocol` is unchanged.
- `BatchResult` construction is unchanged.
- All existing tests pass without modification.
- Four new tests in `TestAnthropicProviderCaching` pass.
- No new dependencies are introduced.

---

## Non-Goals

- Caching the user message (the user message contains batch-specific text and cannot be cached).
- Caching across multiple jobs (Anthropic cache TTL is 5 minutes; cross-job reuse is not guaranteed and not relied upon).
- Adding a feature flag or env-var toggle for caching (caching is always-on; Anthropic silently ignores `cache_control` if the prompt is below the minimum cacheable token count, so there is no error risk).
- Modifying `BatchResult` to expose cache token counts to callers (logging is sufficient for cost observability at this stage).
- Changing `prompt_version` (the prompt content is unchanged; only the API call format changes).

---

## Dependencies

- **external:** `anthropic>=0.84,<1.0` — already in `requirements.txt`. Prompt caching via `cache_control` in the `system` param has been supported since much earlier SDK versions. Version 0.84 is confirmed compatible.
- **internal:** None. Change is self-contained within `provider.py`.

---

## Files

- **modify:** `app/pipeline/translation/provider.py` — change `_call_api` method (steps 1–3), update `translate_batch` unpack and log call (step 4)
- **modify:** `tests/test_pipeline_translation.py` — add `TestAnthropicProviderCaching` test class (step 5)
- **read-only (referenced):** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`

No new files. No other files touched.

---

## Risks

| Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|
| System prompt below Anthropic minimum cacheable token count (1024 tokens for most Claude 3 models) | Low — prompt is ~2500 tokens, well above threshold | Low — Anthropic silently ignores `cache_control` if below minimum; no error, no behavior change | None needed; verify empirically via `cache_creation_tokens > 0` in logs |
| `response.usage` object missing cache fields in some SDK versions | Low — SDK 0.84 exposes these fields | Low — `getattr` fallback to `0` handles this safely | `getattr(usage, "cache_creation_input_tokens", 0)` |
| `system` as a list breaks model compatibility for some Claude models | Low — list format is valid for all Claude 3+ models in production | Medium — if it broke, all batches would fail with a 4xx | The existing error handling (`APIStatusError` → `ContentDeterministicError`) would surface this immediately on the first batch |
| Cache creates non-deterministic behavior between batches | None — caching is read-only and does not change model output | n/a | Prompt caching only affects cost, not model response |

---

## Architectural Notes

- This change is entirely within the LLM integration boundary defined in DEC-003. Only `provider.py` imports or calls the Anthropic client. The change does not cross any pipeline stage boundary.
- The format change (`system` string → system list) is internal to the provider adapter. No stage contract changes. No `pipeline_version` bump required (per DEC-009: "minor internal implementation changes that do not affect stage contracts do not change `pipeline_version`").
- Caching is stateless from the pipeline's perspective: each API call independently carries the `cache_control` header. The Anthropic server manages the cache TTL (5 minutes). No server-side or application-level cache state is introduced, so ARCHITECTURE_GUARDRAILS Rule 6 (hidden caching that alters behavior) is not violated — caching does not alter model output.
- No `docs/DECISIONS.md` entry is required. This is a provider API optimization within an already-approved integration boundary (DEC-003), not a new architectural decision.

---

## Assumptions Made

- The system prompt string passed to `_call_api` is always the full, static system prompt text (never a pre-structured list). Verified by reading `translate_batch`: it calls `self._call_api(system=prompt_template.system, ...)` where `prompt_template.system` is a plain string loaded from YAML via `prompt_loader`.
- Anthropic's `cache_control: {"type": "ephemeral"}` is the correct and current breakpoint type. This is confirmed by Anthropic's public API documentation as of March 2026.
- The system prompt is sufficiently large (~2500 tokens) to meet Anthropic's minimum caching threshold (1024 tokens for Claude 3 Haiku/Sonnet/Opus). If this assumption fails, caching is silently skipped — no error.

---

## Smallest Next Step

Builder modifies `_call_api` in `provider.py` to replace `system=system` with the list format, extends the return tuple, updates the unpack in `translate_batch` and the `provider_batch_ok` log payload, then adds `TestAnthropicProviderCaching` to the test file.

---

## Optional Follow-Ups

- Once caching is live, confirm `cache_read_tokens > 0` in `provider_batch_ok` logs after the first batch of a multi-batch job (this would empirically confirm that caching is active and saving tokens).
- If Anthropic introduces extended cache TTLs or other breakpoint types in future SDK versions, consider upgrading — no code change required, only a `requirements.txt` version bump.
- If `cache_creation_tokens` and `cache_read_tokens` are needed upstream (e.g. for cost ledger accounting per DEC-006), extend `BatchResult` at that time. Current scope: logging only.
