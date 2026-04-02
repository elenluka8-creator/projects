# OPT-COMPACT-JSON — Compact JSON Output Instruction in Translation Prompts

**Task ID:** OPT-COMPACT-JSON  
**Status:** planned  
**Date:** 2026-03-28

---

## Task Restatement

Add a compact-JSON instruction to all three translation prompt YAML files so the LLM emits minimal-whitespace JSON responses, reducing output token cost by an estimated 15–25%.

---

## Background

Output tokens cost 5× more than input tokens ($0.015 vs $0.003/1k with Claude Haiku). The LLM currently returns indented, multi-line JSON. The translation and explanation text content is unchanged — only structural whitespace (indentation, newlines between keys) is removed. This is a pure prompt-side optimisation with no impact on the parsed result.

---

## Plan

### Step 1 — Update `prompts/translation/translate_batch.yaml` [small]

**File:** `prompts/translation/translate_batch.yaml`  
**Current `prompt_version`:** `"1.0"`  
**New `prompt_version`:** `"1.1"`

**Changes:**

1. Bump `prompt_version` to `"1.1"`.

2. Add one rule line to the `system:` Rules section immediately after the existing line:
   `"- Return ONLY a valid JSON object. No preamble, no explanation, no code fences."`

   Insert after it:
   ```
   - Use compact JSON — no indentation, no extra spaces, no newlines between keys or values.
   ```

3. Replace the indented `Required JSON schema:` block with the identical schema in compact form. The schema keys and structure are unchanged; only whitespace is removed.

   **Current (indented):**
   ```
   Required JSON schema:
   {
     "translations": [
       {"id": "<segment_id>", "translated_text": "<translation>"}
     ],
     "new_terms": {"<source_term>": "<target_translation>"},
     "new_entities": {
       "<name>": {"translation": "<translated_name>", "type": "<character|place|organization|other>", "gender": "<m|f|n|none>"}
     },
     "chapter_summary": "<one sentence summary of translated content>"
   }
   ```

   **New (compact):**
   ```
   Required JSON schema:
   {"translations":[{"id":"<segment_id>","translated_text":"<translation>"}],"new_terms":{"<source_term>":"<target_translation>"},"new_entities":{"<name>":{"translation":"<translated_name>","type":"<character|place|organization|other>","gender":"<m|f|n|none>"}},"chapter_summary":"<one sentence summary of translated content>"}
   ```

   **Rationale for compacting the schema example:** The system prompt currently shows an indented schema. Leaving an indented schema example while adding a compact instruction creates a contradictory signal. Presenting the schema in compact form makes the instruction consistent and reinforces the desired output style.

---

### Step 2 — Update `prompts/guided_explanations/guided_batch.yaml` [small]

**File:** `prompts/guided_explanations/guided_batch.yaml`  
**Current `prompt_version`:** `"1.1"`  
**New `prompt_version`:** `"1.2"`

**Changes:**

1. Bump `prompt_version` to `"1.2"`.

2. Add one rule line to the `system:` Rules section immediately after:
   `"- Return ONLY a valid JSON object. No preamble, no explanation, no code fences."`

   Insert after it:
   ```
   - Use compact JSON — no indentation, no extra spaces, no newlines between keys or values.
   ```

3. **No schema example change required.** The guided batch prompt describes its schema in prose (not a JSON code block), so there is no indented example to compact. The prose description is unambiguous alongside the compact instruction.

---

### Step 3 — Update `prompts/translation/analyze_preamble.yaml` [small]

**File:** `prompts/translation/analyze_preamble.yaml`  
**Current `prompt_version`:** `"1.0"`  
**New `prompt_version`:** `"1.1"`

**Changes:**

1. Bump `prompt_version` to `"1.1"`.

2. Add one rule line to the `system:` Rules section immediately after:
   `"- Return ONLY a valid JSON object. No preamble, no explanation, no code fences."`

   Insert after it:
   ```
   - Use compact JSON — no indentation, no extra spaces, no newlines between keys or values.
   ```

3. Replace the indented `Required JSON schema:` block with the identical schema in compact form.

   **Current (indented, lines 18–37):**
   ```
   Required JSON schema:
   {
     "characters": {
       "<original_name>": {
         "translation": "<translated_name_in_target_language>",
         "gender": "<m|f|n|none>",
         "role": "<protagonist|antagonist|supporting|minor>"
       }
     },
     "terminology": {
       "<source_term>": "<target_translation>"
     },
     "places": {
       "<original_name>": {
         "translation": "<translated_name>",
         "type": "<city|country|region|building|fictional|other>"
       }
     },
     "genre_notes": "<one sentence: genre, register, tone of the book>"
   }
   ```

   **New (compact):**
   ```
   Required JSON schema:
   {"characters":{"<original_name>":{"translation":"<translated_name_in_target_language>","gender":"<m|f|n|none>","role":"<protagonist|antagonist|supporting|minor>"}},"terminology":{"<source_term>":"<target_translation>"},"places":{"<original_name>":{"translation":"<translated_name>","type":"<city|country|region|building|fictional|other>"}},"genre_notes":"<one sentence: genre, register, tone of the book>"}
   ```

   The gender values footnote block (lines 40–46) and all prose that follows the schema are unchanged.

---

### Step 4 — Verify parser compatibility [trivial]

**No code change required.**

Both parsing paths in `provider.py` and `preamble.py` handle compact JSON correctly:

- `json.loads(text)` — Python's standard library JSON parser; whitespace is irrelevant to parsing. Handles `{"a":1}` and `{"a": 1}` identically.
- `json_repair.repair_json(text, return_objects=True)` — operates on the token stream, not whitespace. Compact JSON does not affect its repair behaviour.
- `_parse_response` in `provider.py` also handles the case where the model wraps output in markdown fences (`` ```json ... ``` ``). The compact instruction will reduce fence-wrapping likelihood further, but the fence-stripping regex already handles both compact and indented content inside fences.

No changes to `provider.py`, `preamble.py`, or any parser code.

---

### Step 5 — Add a unit test confirming compact JSON parsing [small]

**File:** `tests/test_pipeline_translation.py`

Add a new test class `TestAnthropicProviderParseResponse` with two test cases:

1. `test_parse_response_handles_compact_json` — calls `provider._parse_response()` with a compact JSON string (no whitespace) and asserts the result is a correctly structured dict.

2. `test_parse_response_handles_compact_json_with_fence` — calls `_parse_response()` with a compact JSON string wrapped in a ` ```json ``` ` fence and asserts it is parsed correctly.

These tests exercise the real `_parse_response` code path (not `FakeProvider`) and confirm no regression from the format change.

---

## Acceptance Criteria

- All three prompt YAML files have the compact instruction in their `system:` Rules section.
- All three prompt YAML files have bumped `prompt_version` values (`translate_batch`: `1.1`, `guided_batch`: `1.2`, `analyze_preamble`: `1.1`).
- `translate_batch.yaml` and `analyze_preamble.yaml` schema examples are compact (same keys, no whitespace).
- `guided_batch.yaml` prose schema description is unchanged (no JSON example existed).
- No changes to `provider.py`, `preamble.py`, or any parser code.
- Existing test suite passes unchanged.
- New `TestAnthropicProviderParseResponse` tests pass.

---

## Non-goals

- Changing the JSON schema keys, value types, or structure.
- Compacting the `segments_json` input sent to the LLM in `_build_user_message` (input tokens are 5× cheaper; quality risk of compacting LLM input is not justified).
- Changing any production Python code beyond the three YAML files and the test file.
- Adding new runtime dependencies.
- Changing `provider.py` caching behaviour, retry logic, or API call structure.
- Benchmark measurement (out of scope for this task; tracked separately).

---

## Dependencies

- **external:** none
- **internal:** `app/pipeline/translation/prompt_loader.py` — must continue to load the updated YAML files unchanged; no code changes required. `PromptTemplate` is agnostic to system prompt content.

---

## Files

| Action | Path | Reason |
|--------|------|--------|
| modify | `prompts/translation/translate_batch.yaml` | Add compact instruction, compact schema example, bump version to 1.1 |
| modify | `prompts/guided_explanations/guided_batch.yaml` | Add compact instruction, bump version to 1.2 |
| modify | `prompts/translation/analyze_preamble.yaml` | Add compact instruction, compact schema example, bump version to 1.1 |
| modify | `tests/test_pipeline_translation.py` | Add `TestAnthropicProviderParseResponse` tests |
| read-only | `app/pipeline/translation/provider.py` | Confirmed: `_parse_response` handles compact JSON; no changes needed |
| read-only | `app/pipeline/translation/preamble.py` | Confirmed: `_parse_preamble_response` handles compact JSON; no changes needed |
| read-only | `app/pipeline/translation/prompt_loader.py` | Confirmed: `PromptTemplate` is content-agnostic; no changes needed |
| read-only | `docs/DECISIONS.md` | DEC-003 requires prompt_version bump; DEC-009 records prompt_version in job_run metadata. No new decision record needed. |

---

## Risks

- **Prompt compliance risk (low):** Claude Haiku models reliably follow compact-JSON instructions when the instruction is explicit and the schema example is consistent. The existing "Return ONLY a valid JSON object" rule already trains for structured output; the compact rule is additive. If the model occasionally still returns indented JSON, the parser handles it correctly — no failure mode is introduced.

- **Schema example readability (negligible):** The compact schema in the YAML file is harder to read for humans editing the file. Mitigated by keeping the schema example on a single line that is clearly labelled `Required JSON schema:`.

- **Inconsistent adoption across prompts (low):** All three prompts that reach the LLM boundary are updated in this task. There is no fourth prompt that would be missed.

- **Token savings variability (informational):** Savings depend on response length and structure complexity. Guided mode responses are larger (include `explanations` arrays) and will see proportionally higher absolute token savings. Preamble pass savings are smaller (single call, not per-batch). Expected range: 15–25% output token reduction across translate and guided modes.

---

## Architectural Notes

- DEC-003 requires `prompt_version` to be updated when prompts change in ways that affect pipeline output. Output whitespace removal changes the raw LLM response format (before parsing), so it qualifies. The `job_run` table records `prompt_version` per run, allowing retries and quality comparisons to be scoped to the correct prompt version.
- DEC-009 states in-flight runs use the `prompt_version` from run start. Workers must not silently upgrade prompt versions for in-flight runs. This is handled by the existing `_load_prompt` cache — prompt files are loaded once at worker startup.
- No new architectural decision record is required. This is a prompt optimisation within the existing DEC-003 boundary.

---

## Assumptions Made

- The `segments_json` input (sent to the LLM in the user message) remains indented (`indent=2` in `_build_user_message`). Compacting the input would save input tokens (cheap) at potential quality risk (harder for the LLM to parse). This assumption is safe and consistent with the task constraint.
- No few-shot output examples exist in any of the three prompt files. Confirmed by reading all three files: schemas are structural definitions, not example LLM responses. No additional compact-format example responses need to be added.
- `guided_batch.yaml` schema is intentionally prose-only (not a JSON block). This is a deliberate style difference from `translate_batch.yaml`. No JSON block to compact; prose is unchanged.

---

## Smallest Next Step

Builder should open `prompts/translation/translate_batch.yaml` and apply Step 1 (add compact rule + compact schema example + bump version), then proceed with Steps 2 and 3 for the remaining two YAML files, then Step 5 for the test.

---

## Optional Follow-ups

- **Benchmark measurement:** Run a representative translation batch before and after the change and record token counts per batch to validate the 15–25% output token reduction estimate.
- **Compact the `segments_json` input** (separate task, lower priority): `json.dumps(..., indent=2)` in `_build_user_message` sends indented JSON to the LLM. Removing `indent=2` would reduce input tokens at minimal quality risk (LLM parsers are robust). This should be evaluated separately with a benchmark rather than bundled here.
- **Promote to DEC:** If post-deployment token savings are confirmed at scale, record a formal DEC entry updating DEC-003 to note compact-JSON as the canonical output style for all translation prompts.
