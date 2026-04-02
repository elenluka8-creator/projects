# DISC-2: Further cost reduction without quality loss (multi-model & alternatives)

**Discovery date:** 2026-03-29  
**Status:** complete  
**Related:** `docs/DISC-1-batch-optimization.md`, `docs/DECISIONS.md` (DEC-003 models), `app/config/policy.py`

---

## 1. Executive summary

**Already shipped (baseline):** prompt caching (COST-1), cross-chapter batch merging (COST-2), Express default + copy (COST-3), compact JSON prompts (OPT-1), cache-aware ledger (FIX-5), higher default `MAX_TOKENS_RESPONSE`. Further gains require **product-visible routing** or **benchmarked exceptions** to “one tier → one model”.

**Top three directions worth evaluating next:**

| Direction | Est. savings | Quality risk | Complexity |
|-----------|-------------|--------------|------------|
| **A. Pair-aware default model** (cheap model for “easy” pairs, Sonnet only for `experimental` or user-chosen Standard/Premium) | 30–70% on affected jobs | Medium — must be benchmarked per pair | Medium — policy + benchmarks + UX |
| **B. Mode split** (e.g. Haiku for plain `translate`, Sonnet only for `guided`) | ~40–60% on translate-only traffic | Medium–high — literary / low-resource pairs suffer on Haiku | Low–medium |
| **C. Continue output-side levers** (shorter JSON keys in schema, stricter max explanation length in guided) | 5–15% | Low if tuned carefully | Low |

**Not recommended without major product/architecture change:** per-batch model switching, second cloud LLM provider, Anthropic Batch API for main pipeline (breaks sequential consistency memory).

**Recommendation:** Run a **small benchmark matrix** (same excerpts, blind scoring) for 3–5 high-volume pairs × {Express, Standard} before any automatic pair→model routing. Use existing `_EXPERIMENTAL_PAIRS` + `get_language_pair_tier()` as the hook to **force Sonnet** where data is weak; default **Express or a new “pair tier”** only where benchmarks pass a quality bar.

---

## 2. Multi-model by language pair

### 2.1 Idea

Use **Haiku** for pairs where quality is “good enough” (e.g. en→es, en→de) and **Sonnet** for pairs that are harder (e.g. en→ja, en→zh, low-resource, or literary stress tests).

### 2.2 Fit with current code

- `get_language_pair_tier(source, target)` exists but today only returns `standard` vs `experimental` (`_EXPERIMENTAL_PAIRS` is empty). It does **not** select a model yet.
- `LANGUAGE_CATALOG` already has a per-language `tier` string (`"standard"` for all) — could evolve to `translation_model_profile` or stay separate from UI language tier.
- Model choice today: **`quality_tier` → `TIER_MODELS`** (`get_tier_model`). Any pair-based override must be **explicitly ordered**: e.g. `user tier > pair policy > default`, and must be **logged** (`model_name`, `pair`, `routing_reason`) for support and cost attribution.

### 2.3 Pros

- Large cost spread: Haiku vs Sonnet is often **~4–5×** on list prices; applying only to “safe” pairs cuts average $/book without touching risky pairs.
- Aligns with user mental model if exposed honestly: “Optimized for your language pair” vs “Maximum quality”.

### 2.4 Cons / risks

- **Quality is pair-dependent**, not just “target language”: en→sr vs de→sr differ; literary vs technical text differs. Pair-only routing **without benchmarks** will surprise users.
- **Consistency memory and JSON schema** are identical across models; failures may shift from “hallucination” to “format / omission” on cheaper models — needs monitoring (`translation_quality_issue`, `provider_missing_segment`).
- **Credits and estimates** must match the **effective** model per job (or you undercharge / confuse users).

### 2.5 Verdict

**Promising but conditional.** Implement only after:

1. Define a **frozen allowlist** of `(source, target)` → `routing_profile` (e.g. `economy` = Haiku, `full` = Sonnet).
2. **Benchmark** against current Sonnet baseline on representative excerpts (MQM-lite or internal rubric).
3. Record decision in **`docs/DECISIONS.md`** and expose routing in **admin/analytics** (`model_routing_applied` event).

---

## 3. Multi-model by mode (translate vs guided)

### 3.1 Idea

Always use **Sonnet for `guided`** (heavy JSON + explanations), **Haiku for `translate`** (smaller output, simpler schema).

### 3.2 Pros

- Simple rule, easy to explain.
- Translate mode is a large fraction of volume in many products.

### 3.3 Cons

- **Translate-only** still needs high quality for literary / nuanced texts; Haiku may be **worse** on tone, register, and long-range cohesion — users who pick Standard tier expect Sonnet today.
- Users who chose **Premium** must still get Opus regardless of mode.

### 3.4 Verdict

**Riskier than pair-based routing.** Better as an **optional** “Speed / economy translate” product flag than a silent global switch. If done, it should be **tier-gated**: e.g. only when `quality_tier == express`, keep Standard = Sonnet for both modes.

---

## 4. Other levers (brief)

### 4.1 Output structure (low quality risk)

- **Shorter JSON keys** in API contract (e.g. `t` instead of `translation`) — saves output tokens; requires provider + parser + migration of prompts; test heavily.
- **Guided mode:** cap `explanations` length or count per segment in the prompt — saves output tokens; product must accept shorter glosses.

### 4.2 Second provider (e.g. OpenAI, Gemini)

- **Guardrails:** new external dependency and secret handling → typically requires **escalation** and `DECISIONS.md`.
- Benefit: price competition; cost: adapter maintenance, quality variance, compliance review.

### 4.3 Anthropic Message Batch API

- **Poor fit** for Unfolda’s **sequential** consistency memory (batch N depends on N−1). Could theoretically batch **non-sequential** work only — not applicable to core translate loop.

### 4.4 Two-pass pipelines (draft + refine)

- Theoretically cheaper with small model draft + large model polish; **architecturally heavy**, latency doubles, failure modes multiply. Not MVP.

### 4.5 On-device / open-weights models

- Out of scope for current “single hosted provider” architecture; large quality and ops risk.

---

## 5. What *not* to do (for “no quality loss” claim)

- **Silent downgrade** of model for Standard/Premium tiers.
- **Per-batch** arbitrary model mixing (cohesion and debugging nightmare).
- **Pair routing** without documented benchmarks and rollback.

---

## 6. Recommended next steps (ordered)

1. **Product + Analytics:** Define success metrics (quality rubric, acceptable regression threshold) and event: `translation_model_routed` with `{source_lang, target_lang, quality_tier, model_id, routing_rule_id}`.
2. **Benchmark task (small):** 5 pairs × 10 scenes × 2 models, blind side-by-side; record in `docs/` or `reviews/`.
3. **Architect:** If benchmarks pass for an allowlist, plan minimal change: extend `policy.py` with `PAIR_MODEL_PROFILE` map + single call site in worker/provider init; sync **credit estimator** with effective model.
4. **Optional UX:** Checkbox “Use maximum quality for this language pair” overrides economy routing.

---

## 7. Decision records

| Change | DECISIONS.md |
|--------|----------------|
| Any automatic model selection by pair or mode | New DEC (supplements DEC-003) |
| Second provider | New DEC + ARCHITECTURE update |

---

## 8. Handoff

- **Next agent:** Product (scope + acceptance for benchmark & optional routing), then Analytics Architect (events), then Architect (implementation plan).
- **Task ID (proposed):** DISC-2 complete; follow-up **TASK-82** or similar: “Pair-aware model routing (benchmark-gated)”.

```json
{
  "handoff": {
    "agent": "Discovery",
    "artifact_type": "discovery_report",
    "artifact_path": "docs/DISC-2-cost-reduction-multi-model.md",
    "status": "complete",
    "next_recommended_agent": "Product",
    "next_recommended_reason": "Define benchmark acceptance criteria and whether pair-based routing is user-visible or admin-only.",
    "blocking_issues": [],
    "workflow_state": {
      "task_id": "DISC-2",
      "current_stage": "discovery",
      "analytics_used": false
    }
  }
}
```
