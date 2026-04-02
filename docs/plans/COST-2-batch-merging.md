# COST-2 — Cross-chapter batch merging in batch_planner

**Task ID:** COST-2  
**Author:** Architect  
**Status:** proposed

---

## Task Restatement

Modify `plan_batches()` in `batch_planner.py` to merge consecutive short chapters into a single batch instead of flushing unconditionally at every chapter boundary, reducing wasted Anthropic API calls caused by per-chapter fixed overhead.

---

## Plan

### Step 1 — Add a pre-scan pass to compute per-chapter token totals [small]

Before the main loop, iterate `segments` once to build:

```python
chapter_token_totals: Dict[str, int] = {}
for seg in segments:
    chapter_token_totals[seg.chapter_ref] = (
        chapter_token_totals.get(seg.chapter_ref, 0) + seg.token_estimate
    )
```

This gives the total token count of each chapter, used in step 2 to make the merge/flush decision before the next chapter's segments arrive.

### Step 2 — Replace unconditional chapter-boundary flush with conditional logic [small]

Currently the loop has:

```python
if chapter_changed or would_overflow:
    # flush
```

Replace the `chapter_changed` branch with a conditional flush that respects `TARGET_TOKENS_PER_BATCH`:

```python
if chapter_changed:
    next_chapter_tokens = chapter_token_totals.get(seg.chapter_ref, 0)
    at_target = current_tokens >= TARGET_TOKENS_PER_BATCH
    would_overflow_if_merged = (
        bool(current_ids)
        and current_tokens + next_chapter_tokens > MAX_TOKENS_PER_BATCH
    )
    should_flush = at_target or would_overflow_if_merged
    current_chapter = seg.chapter_ref  # always advance the chapter tracker
elif would_overflow:
    should_flush = True
else:
    should_flush = False
```

### Step 3 — Track `batch_first_chapter` separately from `current_chapter` [small]

`current_chapter` is used only to detect chapter transitions.  
`BatchBoundaryHint.chapter_ref` must be the **first** chapter of the merged batch, so a second variable `batch_first_chapter` is needed:

```
Initialize:
  batch_first_chapter = segments[0].chapter_ref
  current_chapter     = segments[0].chapter_ref

On flush (for any reason):
  emit hint with chapter_ref=batch_first_chapter
  batch_first_chapter = seg.chapter_ref   # new batch starts here
  current_chapter is already updated (step 2)

On merge (no flush despite chapter_changed):
  batch_first_chapter stays unchanged
  current_chapter is updated to seg.chapter_ref
```

### Step 4 — Preserve `chapter_boundaries` correctness [trivial]

No change needed to the existing line:

```python
if seg.chapter_ref not in chapter_boundaries:
    chapter_boundaries[seg.chapter_ref] = batch_index
```

This line runs after the flush decision and after `batch_index` has been incremented (if a flush occurred). When chapters are merged (no flush), `batch_index` is unchanged, so `chapter_boundaries[new_chapter]` correctly records the batch where it first appears alongside the preceding chapters.

### Step 5 — Write unit tests in a new dedicated test file [medium]

Create `tests/test_batch_planner.py` with direct unit tests for `plan_batches()`. See **Tests** section below.

---

## Full Pseudocode

```python
def plan_batches(segments: List[Segment]) -> BatchPlanning:
    if not segments:
        return BatchPlanning(
            chapter_boundaries={},
            batch_boundary_hints=[],
            estimated_batch_count=0,
        )

    # Pre-scan: total tokens per chapter (used to decide merge vs flush)
    chapter_token_totals: Dict[str, int] = {}
    for seg in segments:
        chapter_token_totals[seg.chapter_ref] = (
            chapter_token_totals.get(seg.chapter_ref, 0) + seg.token_estimate
        )

    hints: List[BatchBoundaryHint] = []
    chapter_boundaries: Dict[str, int] = {}

    current_ids: List[str] = []
    current_tokens: int = 0
    batch_first_chapter: str = segments[0].chapter_ref  # chapter_ref for next hint
    current_chapter: str = segments[0].chapter_ref      # tracks the last seen chapter
    batch_index: int = 0

    for seg in segments:
        chapter_changed = seg.chapter_ref != current_chapter
        would_overflow = (
            bool(current_ids)
            and current_tokens + seg.token_estimate > MAX_TOKENS_PER_BATCH
        )

        should_flush = False

        if chapter_changed:
            next_chapter_tokens = chapter_token_totals.get(seg.chapter_ref, 0)
            at_target = current_tokens >= TARGET_TOKENS_PER_BATCH
            would_overflow_if_merged = (
                bool(current_ids)
                and current_tokens + next_chapter_tokens > MAX_TOKENS_PER_BATCH
            )
            should_flush = at_target or would_overflow_if_merged
            current_chapter = seg.chapter_ref   # advance regardless of flush decision
        elif would_overflow:
            should_flush = True

        if should_flush and current_ids:
            hints.append(
                BatchBoundaryHint(
                    batch_index=batch_index,
                    segment_ids=list(current_ids),
                    token_total=current_tokens,
                    chapter_ref=batch_first_chapter,
                )
            )
            batch_index += 1
            current_ids = []
            current_tokens = 0
            batch_first_chapter = seg.chapter_ref

        # Record the first batch index for this chapter
        if seg.chapter_ref not in chapter_boundaries:
            chapter_boundaries[seg.chapter_ref] = batch_index

        current_ids.append(seg.id)
        current_tokens += seg.token_estimate

    # Final flush
    if current_ids:
        hints.append(
            BatchBoundaryHint(
                batch_index=batch_index,
                segment_ids=list(current_ids),
                token_total=current_tokens,
                chapter_ref=batch_first_chapter,
            )
        )

    return BatchPlanning(
        chapter_boundaries=chapter_boundaries,
        batch_boundary_hints=hints,
        estimated_batch_count=len(hints),
    )
```

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Single chapter < TARGET | One batch; no flush at chapter boundary |
| Single chapter = TARGET | One batch; flush at the next chapter boundary (at_target = True) |
| Single chapter > MAX | Mid-chapter splits via `would_overflow`; `batch_first_chapter` = that chapter throughout all splits |
| Many tiny chapters, none reaching TARGET | All merged into one batch until `would_overflow_if_merged` triggers |
| Two chapters whose combined total = MAX | Merged into one batch (not exceeding MAX) |
| Two chapters whose combined total > MAX | Flush before the second chapter starts |
| Chapter that individually > MAX | Flushed before it starts (if current_tokens > 0), then split mid-chapter |
| Empty segments list | Returns empty BatchPlanning (unchanged from current) |
| Single segment | One batch (unchanged from current) |
| `current_ids` empty at chapter boundary | `would_overflow_if_merged` is False (guarded by `bool(current_ids)`); no spurious flush |

---

## Acceptance Criteria

1. `plan_batches(segments)` public signature is unchanged.
2. All segments appear in exactly one batch hint (no segments lost or duplicated).
3. No batch hint's `token_total` exceeds `MAX_TOKENS_PER_BATCH`.
4. `estimated_batch_count == len(batch_boundary_hints)`.
5. `chapter_boundaries[chapter_ref]` equals the `batch_index` of the first hint containing that chapter's segments.
6. `BatchBoundaryHint.chapter_ref` is the chapter_ref of the first segment in that batch.
7. A book with 10 chapters of 200 tokens each (TARGET=2000, MAX=4000) produces at most 1 batch (all chapters merged), not 10.
8. A book with 10 chapters of 300 tokens each (TARGET=2000, MAX=4000) produces batches of approximately 6–7 chapters (≤4000 tokens each), not 10.
9. A chapter exceeding MAX_TOKENS_PER_BATCH is still correctly split mid-chapter.
10. Existing `TestBatchPlanning` tests in `test_pipeline_segmentation.py` continue to pass without modification.

---

## Non-goals

- Do not change `MAX_TOKENS_PER_BATCH` default (4000).
- Do not change `TARGET_TOKENS_PER_BATCH` default (2000).
- Do not change the `Segment`, `BatchBoundaryHint`, `BatchPlanning`, or `SegmentCollection` models.
- Do not change `segmentation/stage.py` or any other pipeline module.
- Do not add any new external dependencies.
- Do not implement any DB migration (batch planning is recomputed at job creation).
- Do not add analytics instrumentation (this is an internal algorithmic optimization with no user-facing behavior change).

---

## Tests

Create `tests/test_batch_planner.py` as a dedicated unit test file for `plan_batches()`.

### Test cases to implement

**`TestBatchPlannerMergeSmallChapters`**

1. **`test_two_tiny_chapters_merged_into_one_batch`**  
   Two chapters, each 200 tokens (TARGET=2000, MAX=4000). Assert `estimated_batch_count == 1` and both chapter_refs appear in `chapter_boundaries` with index 0.

2. **`test_ten_tiny_chapters_merged_efficiently`**  
   Ten chapters × 200 tokens = 2000 total (TARGET=2000, MAX=4000). All merged into one batch.

3. **`test_chapter_boundary_flush_when_at_target`**  
   Chapters A (2000 tokens) then B (200 tokens). Assert A flushes before B starts → 2 batches. Assert `chapter_boundaries["B"] == 1`.

4. **`test_chapter_boundary_flush_when_merge_would_overflow`**  
   Current batch = 3500 tokens (chapters already merged), next chapter = 600 tokens (3500+600 > 4000). Assert flush before next chapter.

5. **`test_chapter_boundaries_map_correct_on_merge`**  
   Chapters A (100 tokens), B (100 tokens), C (2000 tokens). A+B merge into batch 0. C flushes to batch 1. Assert `chapter_boundaries == {"A": 0, "B": 0, "C": 1}`.

6. **`test_batch_hint_chapter_ref_is_first_merged_chapter`**  
   Chapters A (100 tokens), B (100 tokens) merged into one batch. Assert `hints[0].chapter_ref == "A"`.

**`TestBatchPlannerMidChapterSplit`**

7. **`test_large_single_chapter_split_mid_chapter`**  
   One chapter, 5000 tokens (MAX=4000). Must produce ≥2 batches; all segment IDs present; no batch exceeds MAX.

8. **`test_large_chapter_after_small_merged_chapters`**  
   Chapters A+B (100 tokens each, merged), then chapter C (5000 tokens, split). Assert C is split across multiple batches; `chapter_boundaries["C"]` points to the correct batch index.

**`TestBatchPlannerEdgeCases`**

9. **`test_empty_segments_returns_empty_planning`**  
   `plan_batches([]) → BatchPlanning(chapter_boundaries={}, batch_boundary_hints=[], estimated_batch_count=0)`.

10. **`test_single_segment_single_batch`**  
    One segment → one hint, `estimated_batch_count == 1`.

11. **`test_no_batch_exceeds_max_tokens`**  
    50 chapters × 100 tokens each (TARGET=2000, MAX=4000). Assert all hints have `token_total <= MAX_TOKENS_PER_BATCH`.

12. **`test_all_segments_appear_exactly_once`**  
    Parameterised across a mix of large and small chapters. All `seg.id` values appear in exactly one hint's `segment_ids`.

13. **`test_target_and_max_from_env_respected`**  
    Patch `batch_planner.TARGET_TOKENS_PER_BATCH = 500` and `batch_planner.MAX_TOKENS_PER_BATCH = 1000`. Three chapters × 600 tokens → each chapter exceeds TARGET; each must be its own batch.

---

## Dependencies

- **external:** none
- **internal:** `app.pipeline.segmentation.models` (read-only; no changes)

---

## Files

| Action | Path | Reason |
|---|---|---|
| modify | `app/pipeline/segmentation/batch_planner.py` | Implement conditional chapter-boundary flush |
| create | `tests/test_batch_planner.py` | Dedicated unit tests for `plan_batches()` |
| read-only | `app/pipeline/segmentation/models.py` | Reference for `BatchBoundaryHint`, `BatchPlanning`, `Segment` |
| read-only | `tests/test_pipeline_segmentation.py` | Existing tests that must continue to pass |

---

## Risks

- **Regression in existing tests:** `TestBatchPlanning` in `test_pipeline_segmentation.py` exercises `plan_batches()` indirectly through `segment()`. The test `test_single_short_document_is_one_batch` and `test_all_segments_appear_in_hints` should pass unchanged. Verify before merge.
- **Token estimate inaccuracy:** `chapter_token_totals` is computed from `seg.token_estimate` (a heuristic). If the estimate is significantly wrong, a merged batch could slightly exceed MAX in the LLM call. This is an existing limitation of the heuristic, not introduced by this change.
- **`would_overflow_if_merged` is conservative:** When the next chapter's total exceeds what would fit in the current batch, we flush before that chapter starts — even if the chapter itself would get split and only its first portion would have been added. This is intentional: it avoids counting on mid-chapter split behavior to bail out overflow at chapter boundaries.

---

## Architectural Notes

- This change is fully contained within the segmentation stage. No pipeline boundary is crossed.
- The public API (`plan_batches(segments) -> BatchPlanning`) and all data contracts are unchanged.
- The change is backward-compatible: batch planning runs only at job creation, so jobs already in progress use their pre-computed `BatchPlanning` and are unaffected.
- `TARGET_TOKENS_PER_BATCH` was previously defined but unused. This change makes it active. Its default (2000) and the `MAX_TOKENS_PER_BATCH` default (4000) remain unchanged.
- No decision record is required: this does not change pipeline boundaries, data contracts, or introduce new dependencies.

---

## Assumptions Made

- `segments` are ordered: all segments of a chapter appear contiguously (i.e., chapter boundaries are never interleaved). This is implied by the segmentation stage contract and the current planner's design.
- `seg.token_estimate >= 1` for all segments (enforced by `_estimate_tokens` in `stage.py`).
- The pre-scan pass (O(n)) is acceptable; segments lists are bounded by book length and are processed in memory.

---

## Smallest Next Step

Builder modifies `plan_batches()` in `app/pipeline/segmentation/batch_planner.py` per the pseudocode in Step 2–3, then creates `tests/test_batch_planner.py` with the 13 test cases listed above.

---

## Optional Follow-ups

- Add a `merged_chapter_count` field to `BatchBoundaryHint` for observability (out of scope for COST-2).
- Expose `chapter_token_totals` as a field on `BatchPlanning` for downstream cost-estimation use (out of scope).
- Tune `TARGET_TOKENS_PER_BATCH` default based on empirical data from production jobs.
