# DISC-1: Translation Pipeline Batch Optimization

**Discovery date:** 2026-03-28  
**Author:** Discovery agent  
**Status:** Complete  
**Linked task:** COST-4 (proposed)

---

## 1. Executive Summary

Three findings stand out above all others.

**Finding 1 — MAX_TOKENS_RESPONSE is dangerously low (reliability bug, not an optimization)**  
The code default is `MAX_TOKENS_RESPONSE = 8,192`, not the 32,768 cited in the brief. For guided mode with 4,000-token batches, expected output is ≈ 16,000 tokens — double the hard cap. This silently triggers JSON truncation, json_repair fallback, and retry cycles. For translate mode at full 4,000-token batches, output ≈ 6,000–8,000 tokens, leaving only 0–25% headroom. **This is the highest-priority fix.**

**Finding 2 — Output tokens cost ≈ 88% of total; batch size changes save < 2%**  
Modelling the cost function shows that output cost is nearly constant regardless of batch size (it scales with total content, not call count). Overhead savings from larger batches flatten sharply after 4,000 content tokens — going from 4,000 → 8,000 tokens saves approximately 1.5% total cost. The current 4,000 limit is already near-optimal for translate mode.

**Finding 3 — Compact JSON output is the highest-leverage cost lever**  
LLMs often produce indented JSON output (whitespace, newlines). Requesting compact JSON in the prompt could save 15–25% of output tokens, which at 88% output cost share translates to a 13–22% total cost reduction with zero quality impact and zero architecture change.

**Estimated combined impact of all recommendations:**  
Reliability fix (raise MAX_TOKENS) + compact JSON output: ~15–20% cost reduction + elimination of JSON truncation errors.

---

## 2. Batch Size Analysis

### 2.1 MAX_TOKENS_RESPONSE discrepancy

The task brief states `MAX_TOKENS_RESPONSE = 32768`. The code says:

```python
# app/pipeline/translation/provider.py line 43
MAX_TOKENS_RESPONSE: int = int(os.environ.get("TRANSLATION_MAX_TOKENS_RESPONSE", "8192"))
```

Default is **8,192**. This is the operative limit unless overridden in the environment.

### 2.2 Output token ratio from production data

Back-calculating from Wuthering Heights production data:

| Metric | Value |
|--------|-------|
| Total API calls | 84 |
| Avg tokens_in | 5,067 |
| Estimated overhead (system prompt + memory avg) | ~3,300 tokens |
| Estimated content tokens/call | ~1,770 |
| Total input cost | 84 × 5,067 × $0.003/1k = **$1.28** |
| Observed total cost | $10.59 |
| Output cost implied | $10.59 − $1.28 = **$9.31 (88%)** |
| Avg output tokens/call | $9.31 / (84 × $0.015/1k) = **7,390 tokens** |
| **Output/content ratio** | 7,390 / 1,770 = **~4.2×** |

The 4.2× ratio is consistent with guided mode (translations + explanations + JSON structure) or compact source language translated to a verbose target language. For pure translate mode with compact JSON, a 1.5–2.5× ratio is expected. The high observed ratio suggests production runs include guided mode, or the LLM outputs indented JSON that inflates token count significantly.

**Key insight:** output cost is 88% of total and scales with total content tokens, not call count.

### 2.3 Cost model at different MAX_TOKENS_PER_BATCH

Model assumptions:
- 100k-word English book: ≈ 125,000 content tokens
- Overhead per call: 2,500 tokens system prompt (cached) + 1,000 tokens consistency memory (avg, uncached)
- COST-1 active: cached tokens at $0.0003/1k, uncached at $0.003/1k
- Output ratio: 2.0× for translate mode, 4.0× for guided mode

#### Translate mode (output ratio 2.0×):

| Content/batch | n_calls | Input cost | Output cost | Total |
|---|---|---|---|---|
| 2,000 | 63 | $0.55 | $3.75 | **$4.30** |
| 4,000 | 32 | $0.46 | $3.75 | **$4.21** |
| 6,000 | 21 | $0.43 | $3.75 | **$4.18** |
| 8,000 | 16 | $0.42 | $3.75 | **$4.17** |
| 10,000 | 13 | $0.41 | $3.75 | **$4.16** |

**Savings from 4,000 → 8,000:** $0.04 on $4.21 = **1.0%**  
**Savings from 4,000 → 6,000:** $0.03 on $4.21 = **0.7%**

The output cost ($3.75) is invariant with batch size — it always equals `content_total × output_ratio × $0.015/1k`. Only the overhead cost (driven by call count) changes, and it is a small fraction of total.

#### Cost crossover formula:

Total cost = `overhead_per_call × n_calls × per_token_rate + content_total × output_ratio × output_rate`

The second term is constant. The first term → 0 as batch size → ∞. **There is no crossover point where larger batches become more expensive — cost strictly decreases and then flattens.** The useful range is 3,000–6,000 tokens; beyond that, savings are under 1%.

#### Guided mode (output ratio 4.0×):

| Content/batch | n_calls | Output tokens/call | Safe with 8,192 limit? |
|---|---|---|---|
| 1,500 | 84 | 6,000 | ✅ 27% headroom |
| 2,000 | 63 | 8,000 | ⚠️ 2% headroom (risky) |
| 2,500 | 50 | 10,000 | ❌ exceeds 8,192 |
| 4,000 | 32 | 16,000 | ❌ far exceeds 8,192 |

**For guided mode, the current MAX_TOKENS_RESPONSE=8,192 is insufficient at any practical batch size.** Even 2,000 content tokens leaves only 192 tokens of headroom.

### 2.4 Safe ceiling analysis

| MAX_TOKENS_RESPONSE | Safe max content (translate, 2.5× ratio) | Safe max content (guided, 4.0× ratio) |
|---|---|---|
| 8,192 (current) | 3,277 | 2,048 |
| 16,384 | 6,554 | 4,096 |
| 32,768 | 13,107 | 8,192 |

**Recommendation for MAX_TOKENS_RESPONSE:** Raise to **16,384** as the baseline. This safely accommodates:
- Translate mode at 4,000 content tokens with 64% headroom
- Guided mode at 4,000 content tokens with marginal headroom (requires monitoring)

For guided mode at high explanation density, raise to **32,768** (or set per-mode via env var).

### 2.5 Recommendation for MAX_TOKENS_PER_BATCH

**Keep at 4,000 tokens for translate mode.** The cost curve analysis confirms this is near-optimal with diminishing returns above this point. The safety profile is good once MAX_TOKENS_RESPONSE is raised to 16,384.

**Lower to 2,000–2,500 tokens for guided mode** if MAX_TOKENS_RESPONSE remains at 8,192. If MAX_TOKENS_RESPONSE is raised to 32,768, guided mode can safely use 4,000 tokens.

---

## 3. Parallelism Analysis

### 3.1 What is blocked

The `ConsistencyMemory` is updated after every batch (`translate_batch` returns `new_terms`, `new_entities`, `chapter_summary` which are merged into memory before the next batch begins). This creates a strict serial dependency chain:

```
batch_0 → memory_0 → batch_1 → memory_1 → batch_2 → ...
```

**Intra-chapter parallelism:** not possible. Segments within a chapter are ordered and each batch within a chapter depends on the previous batch's memory update.

**Chapter-parallel processing:** architecturally possible (process chapters independently with no memory sharing), but would break cross-chapter terminology consistency. DEC-005 explicitly mandates job-scoped consistency memory. This option violates the architecture.

**Request pre-fetching:** to pre-fetch batch N+1 while batch N is in flight, you would need to predict the memory state that batch N will produce. This requires speculative execution or speculation-aware prompt design, both of which introduce non-determinism. Not recommended.

### 3.2 What could be parallelised safely

**Independent books/jobs:** already handled by the worker pool. Multiple users' jobs run in parallel.

**Preamble + batch_0 overlap:** not safe. The preamble analysis produces the initial `ConsistencyMemory` that seeds batch_0. batch_0 cannot start until the preamble completes. The current sequential design is correct.

**Post-processing (formatting stage):** the formatting stage receives completed `TranslatedSegment` collections and could in principle process chapters in parallel, but this is downstream of translation and outside the scope of this discovery.

### 3.3 Conclusion

**No safe parallelism is possible within the sequential translation loop.** The current architecture is correct. Parallelism attempts within the translation stage would violate DEC-005's consistency memory model.

---

## 4. Consistency Memory Analysis

### 4.1 Current state

```python
# consistency.py
_MAX_CONTEXT_CHARS: int = 2000  # hard cap on prompt context string
_MAX_TERMS: int = 200           # max terminology map entries
_MAX_ENTITIES: int = 150        # max named entity registry entries
```

The context string exposed to the prompt is limited to 2,000 characters. At ~4 chars/token, this is ~500 tokens of overhead per batch — modest and well-controlled.

`to_context_string()` serialises only the **top 30 terms** (by hit count) and **top 20 entities** (by hit count), even though the internal maps can hold 200 terms and 150 entities. This means:

- The internal maps can grow large, but the prompt cost stays constant.
- The 2,000-char cap is a safety net for edge cases, not a routine limiter.
- Late-book batches have no more prompt overhead than early batches (the context is truncated to the same 2,000 chars regardless of memory size).

### 4.2 LFU eviction

Person-type entities are never evicted (protected). Non-person entities and terms are evicted LFU when the maps exceed their limits. This is a good design — character names are the most important consistency targets in fiction, and they are preserved.

### 4.3 Improvement opportunities

**Minor: hit-count accuracy.** The hit count increments when a term is seen again in a new batch, but does not weight by how many times it appeared within a batch. A term appearing 50 times in one batch gets the same +1 as a term appearing once. This could be improved but the impact on translation quality is minimal.

**None significant for cost:** the consistency memory overhead (≈500 tokens) is small relative to content tokens and invariant with book length. No meaningful cost optimisation available here.

**Assessment:** `_MAX_CONTEXT_CHARS`, `_MAX_TERMS`, and `_MAX_ENTITIES` are already well-tuned for books up to ~200k words. No changes recommended.

---

## 5. Other Opportunities

### 5.1 Compact JSON output (highest-leverage quick win)

The input JSON to the API is formatted with `indent=2`:

```python
# provider.py line 326
segments_json = json.dumps(..., indent=2)
```

This is input formatting — the LLM reads nicely indented JSON. However, the LLM may respond with indented JSON in its output too (particularly if the prompt examples show indented JSON or if no explicit instruction is given). Indented JSON output adds 15–25% of tokens as whitespace.

**Recommendation:** Add an explicit instruction to the translation prompt templates to output compact JSON (no whitespace, no indentation). This is a prompt-only change affecting no code.

Estimated saving: 15–25% of output tokens × 88% output cost share = **13–22% total cost reduction**.

This is purely a prompt change and does not require architectural review. It requires a `prompt_version` bump and quality validation.

### 5.2 Preamble: runtime bug from COST-1 (blocker)

`preamble.py` line 176 unpacks only 4 return values from `_call_api`:

```python
raw, tokens_in, tokens_out, latency_ms = provider._call_api(
    system=template.system, user=user_message, timeout_seconds=120.0,
)
```

But after COST-1, `_call_api` returns **6 values**:

```python
# provider.py line 414
return text, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms
```

This will raise `ValueError: too many values to unpack` at runtime for every book over 5,000 words. **This is a bug introduced by COST-1 that must be fixed before pushing.**

Fix: update the unpacking in `preamble.py` to:
```python
raw, tokens_in, tokens_out, _cache_creation, _cache_read, latency_ms = provider._call_api(...)
```

Or log the cache tokens for preamble observability:
```python
raw, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms = provider._call_api(...)
```

### 5.3 Preamble: reduce max_tokens

The preamble call uses the global `MAX_TOKENS_RESPONSE = 8,192` for `max_tokens`. The preamble response only needs ≈500–1,000 tokens (JSON with characters, places, terms, genre note). Setting `max_tokens=2048` for the preamble call would:

- Slightly reduce worst-case output cost on preamble (one call, minor impact).
- Reduce the risk of the LLM generating verbose preamble output that inflates cost.
- No quality impact (the output schema is compact by design).

**Implementation:** `_call_api` should accept an optional `max_tokens` override, or the preamble call should pass a per-call limit.

### 5.4 Input JSON indent removal (minor input saving)

The `indent=2` on input segments JSON adds whitespace tokens to every batch input. Removing it (`indent=None`) reduces input tokens by ~5–10%. At 12% input cost share, this saves ~0.6–1.2% total. Low priority, but free.

### 5.5 Segment ID verbosity

Current segment IDs like `seg_ch001_p023_s04` are 17–20 characters. These appear in both input and output JSON (once per segment, twice if the output echoes the ID). Shortening IDs (e.g., `s1234`) could reduce token count slightly. The savings are small and ID format is likely constrained by downstream stages. Low priority.

### 5.6 TARGET_TOKENS_PER_BATCH tuning (COST-2 effect)

With COST-2's cross-chapter merging:
- `TARGET_TOKENS_PER_BATCH = 2,000`: batches flush at or above 2,000 tokens when crossing a chapter boundary.
- `MAX_TOKENS_PER_BATCH = 4,000`: absolute hard cap.

Raising `TARGET_TOKENS_PER_BATCH` to 3,000 (keeping MAX at 4,000) would reduce the number of sub-optimal flushes at chapter boundaries where the current batch is between 2,000 and 3,000 tokens. This better fills batches and reduces call count without changing the hard cap. Low implementation risk — pure configuration change.

### 5.7 Retry delay tuning

Current retry delays: `[1.0, 2.0, 4.0]` seconds. For rate-limit errors from Anthropic, the actual retry-after header is more informative. If the provider returns a `Retry-After` header, using it would reduce unnecessary wait time. Low priority for MVP.

---

## 6. Recommended Next Steps (by expected ROI)

| Priority | Action | Type | Complexity | Estimated saving |
|---|---|---|---|---|
| 1 | **Fix preamble unpack bug** (§5.2) | Bug fix | Trivial (1 line) | Blocks all production use |
| 2 | **Raise MAX_TOKENS_RESPONSE to 16,384** | Config change | Trivial (env var + default) | Eliminates truncation errors |
| 3 | **Request compact JSON output in prompts** | Prompt change | Low (prompt edit + version bump) | 13–22% total cost |
| 4 | **Raise TARGET_TOKENS_PER_BATCH to 3,000** | Config tuning | Trivial (env var change + test) | ~0.5–1% cost, fewer calls |
| 5 | **Add per-mode MAX_TOKENS_RESPONSE** | Config refactor | Low (env var split + provider logic) | Guided mode reliability |
| 6 | **Preamble: cap max_tokens at 2,048** | Minor code change | Low | <1% cost on preamble |
| 7 | **Remove indent=2 from input segments JSON** | Minor code change | Trivial | ~0.6–1.2% total cost |

Items 1 and 2 are reliability fixes and should be included in the COST-1/COST-2/COST-3 push.  
Item 3 is the highest-leverage pure optimization and should be the next dedicated cost task.

---

## 7. Decision Records Needed

### Must record before implementation:

**DEC-0XX — MAX_TOKENS_RESPONSE raised to 16,384 (or 32,768 for guided mode)**  
This changes provider configuration behaviour and affects pipeline reliability and cost. Requires a decision record because it changes the translate stage's provider call parameters in a way that affects cost accounting and retry semantics (DEC-005, DEC-006, DEC-007).

**DEC-0YY — Compact JSON output instruction in translation prompts**  
Prompt changes affecting pipeline behaviour require a decision record per DEC-003 (§Consequences: "Prompt changes that affect pipeline behaviour become architecture-relevant changes") and a `prompt_version` bump. The compact JSON change is a prompt strategy change that reduces output token count — this crosses the threshold for a decision record.

### Do NOT need a decision record:

- Fixing the preamble unpack bug — implementation error fix, not an architectural change.
- Raising `TARGET_TOKENS_PER_BATCH` from 2,000 to 3,000 — configuration tuning within the bounds of DEC-005's existing batch strategy.
- Removing `indent=2` from input JSON — internal implementation detail.
- Setting a smaller `max_tokens` for the preamble call — implementation detail, not a strategy change.

---

## 8. Assumptions Made

1. The production cost data predates COST-1/COST-2/COST-3 deployments. After these changes, per-call overhead decreases (caching) and call count decreases (batch merging), which shifts cost further toward output dominance. The directional findings remain valid and likely strengthen.

2. The observed output/content ratio of ~4.2× from Wuthering Heights production data includes guided mode runs or significant JSON whitespace inflation. For pure translate mode with compact JSON, the ratio is likely 1.5–2.5×. This does not change the recommendation to raise MAX_TOKENS_RESPONSE.

3. `_MAX_CONTEXT_CHARS = 2000` fully contains the consistency context in nearly all batches. The cap functions as a safety net rather than a routine limiter.

4. The preamble prompt (`translation/analyze_preamble.yaml`) does not have access to the Anthropic caching benefit that helps translation batches, because the preamble system prompt is unique per book configuration. This is expected and the cost is acceptable (~$0.06–0.08 fixed overhead per book).

---

## Handoff Block

```json
{
  "agent": "discovery",
  "artifact": "docs/DISC-1-batch-optimization.md",
  "artifact_type": "discovery_report",
  "status": "complete",
  "next_agent": "iteration-manager",
  "summary": "Batch size is near-optimal at 4,000 tokens (diminishing returns above this). The critical findings are: (1) MAX_TOKENS_RESPONSE=8,192 is a reliability bug — must raise to 16,384+; (2) preamble.py has a runtime crash bug from COST-1 (value unpack mismatch); (3) compact JSON output instruction in prompts is the highest-leverage cost lever (~13-22% saving). No parallelism is possible without violating DEC-005. Consistency memory is well-tuned.",
  "decisions_needed": [
    "DEC-0XX: raise MAX_TOKENS_RESPONSE to 16384 (or per-mode)",
    "DEC-0YY: compact JSON output instruction in translation prompts (prompt_version bump)"
  ],
  "bugs_found": [
    "preamble.py line 176: _call_api returns 6 values; unpacking expects 4 — will crash at runtime for any book > 5,000 words (introduced by COST-1)"
  ],
  "blocking_items": [
    "Preamble unpack bug must be fixed before COST-1/COST-2/COST-3 are pushed to production"
  ]
}
```
