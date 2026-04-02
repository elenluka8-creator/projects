# COST-2 Review — Cross-chapter batch merging in batch_planner

**Reviewer:** Reviewer agent  
**Date:** 2026-03-28  
**Task:** COST-2  
**Plan:** `docs/plans/COST-2-batch-merging.md`

---

## Review Result

Status: **APPROVED**

---

## Scope Check

**Plan adherence — all steps implemented:**

| Plan Step | Implemented |
|---|---|
| Step 1 — Pre-scan pass for `chapter_token_totals` | ✅ Exact match to plan pseudocode (lines 47–51) |
| Step 2 — Conditional chapter-boundary flush | ✅ Exact match to plan pseudocode (lines 63–81) |
| Step 3 — `batch_first_chapter` tracked separately | ✅ Initialized correctly (line 58), updated on flush (line 95), unchanged on merge |
| Step 4 — `chapter_boundaries` correctness preserved | ✅ No change to existing logic (lines 98–99) |
| Step 5 — `tests/test_batch_planner.py` created with 13 tests | ✅ All 13 tests present and passing |

**Files changed:** Only `app/pipeline/segmentation/batch_planner.py` and `tests/test_batch_planner.py`. No other files touched. Scope is correct.

**Non-goals respected:**
- `MAX_TOKENS_PER_BATCH` default (4000) unchanged ✅
- `TARGET_TOKENS_PER_BATCH` default (2000) unchanged ✅
- `Segment`, `BatchBoundaryHint`, `BatchPlanning`, `SegmentCollection` models unchanged ✅
- `segmentation/stage.py` not touched ✅
- No new external dependencies ✅
- No analytics instrumentation added ✅

---

## Architecture Check

The change is fully contained within `app/pipeline/segmentation/batch_planner.py`. No pipeline stage boundary is crossed. The public API `plan_batches(segments: List[Segment]) -> BatchPlanning` is unchanged. No hidden coupling to other stages was introduced.

`chapter_boundaries` correctness is preserved: the recording line (`if seg.chapter_ref not in chapter_boundaries: chapter_boundaries[seg.chapter_ref] = batch_index`) executes after `batch_index` has been incremented for any flush, so new chapters always receive the correct first-batch index. For mid-chapter splits (same `chapter_ref`), the entry is already present and is not overwritten — the first batch index for that chapter is preserved correctly.

---

## Prompt Integrity

No prompt templates in this change. Not applicable.

---

## AI / LLM Check

No model names, providers, or token logging in this module. Not applicable.

---

## Code Quality

The implementation is clean and minimal. Logic is structured in a single linear scan with a pre-scan pass — O(n) total. The three flush conditions (at target, overflow-if-merged, mid-chapter overflow) are clearly separated and correspond 1:1 to the plan's pseudocode.

The `DEC-005` reference in the module docstring (`# Batch strategy (per DEC-005)`) is valid — DEC-005 exists in `docs/DECISIONS.md` as the long-book processing and consistency strategy decision.

One cosmetic observation: the first line of the module docstring (`Groups segments into chapter-scoped, token-bounded translation batches.`) is slightly stale — batches can now span multiple chapters. The detailed strategy block that follows (lines 5–13) is accurate. This is purely cosmetic and does not affect correctness.

---

## Dependencies

No new dependencies. Standard library only (`os`, `typing`).

---

## Tests

All 36 tests pass (13 new, 23 existing):

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
collected 36 items

tests/test_batch_planner.py::TestBatchPlannerEdgeCases::test_empty_segments_returns_empty_planning PASSED
tests/test_batch_planner.py::TestBatchPlannerEdgeCases::test_single_segment_single_batch PASSED
tests/test_batch_planner.py::TestBatchPlannerEdgeCases::test_no_batch_exceeds_max_tokens PASSED
tests/test_batch_planner.py::TestBatchPlannerEdgeCases::test_all_segments_appear_exactly_once PASSED
tests/test_batch_planner.py::TestBatchPlannerEdgeCases::test_target_and_max_from_module_constants_respected PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_two_tiny_chapters_merged_into_one_batch PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_ten_tiny_chapters_merged_efficiently PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_chapter_boundary_flush_when_at_target PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_chapter_boundary_flush_when_merge_would_overflow PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_chapter_boundaries_map_correct_on_merge PASSED
tests/test_batch_planner.py::TestBatchPlannerMergeSmallChapters::test_batch_hint_chapter_ref_is_first_merged_chapter PASSED
tests/test_batch_planner.py::TestBatchPlannerMidChapterSplit::test_large_single_chapter_split_mid_chapter PASSED
tests/test_batch_planner.py::TestBatchPlannerMidChapterSplit::test_large_chapter_after_small_merged_chapters PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_returns_segment_collection PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_guided_mode_accepted PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_paragraphs_split_by_newline PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_empty_lines_filtered_out PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_segment_has_required_fields PASSED
tests/test_pipeline_segmentation.py::TestBasicSegmentation::test_token_estimate_at_least_one PASSED
tests/test_pipeline_segmentation.py::TestSegmentIdStability::test_same_doc_same_ids PASSED
tests/test_pipeline_segmentation.py::TestSegmentIdStability::test_different_doc_id_different_seg_ids PASSED
tests/test_pipeline_segmentation.py::TestSegmentIdStability::test_all_segment_ids_unique PASSED
tests/test_pipeline_segmentation.py::TestMultiChapterDocument::test_chapter_refs_assigned PASSED
tests/test_pipeline_segmentation.py::TestMultiChapterDocument::test_chapter_boundaries_in_batch_planning PASSED
tests/test_pipeline_segmentation.py::TestMultiChapterDocument::test_fallback_chapter_ref_when_no_chapter_refs PASSED
tests/test_pipeline_segmentation.py::TestErrorCases::test_empty_text_raises_segmentation_error PASSED
tests/test_pipeline_segmentation.py::TestErrorCases::test_invalid_mode_raises_segmentation_error PASSED
tests/test_pipeline_segmentation.py::TestSubSegmentation::test_large_paragraph_produces_multiple_segments_with_shared_paragraph_id PASSED
tests/test_pipeline_segmentation.py::TestSubSegmentation::test_large_paragraph_all_text_preserved PASSED
tests/test_pipeline_segmentation.py::TestBatchPlanning::test_no_batch_exceeds_max_tokens PASSED
tests/test_pipeline_segmentation.py::TestBatchPlanning::test_all_segments_appear_in_hints PASSED
tests/test_pipeline_segmentation.py::TestBatchPlanning::test_estimated_batch_count_matches_hints PASSED
tests/test_pipeline_segmentation.py::TestBatchPlanning::test_single_short_document_is_one_batch PASSED
tests/test_pipeline_segmentation.py::TestTokenEstimate::test_token_estimate_roughly_proportional_to_text_length PASSED
tests/test_pipeline_segmentation.py::TestTokenEstimate::test_token_estimate_minimum_one PASSED
tests/test_pipeline_segmentation.py::TestTokenEstimate::test_segment_collection_token_sum_reasonable PASSED

============================== 36 passed in 0.05s ==============================
```

**Coverage of plan acceptance criteria:**

| AC | Criterion | Covered by test |
|---|---|---|
| AC1 | Public signature unchanged | Structural — verified by compile + all passing tests |
| AC2 | All segments in exactly one hint | `test_all_segments_appear_exactly_once` |
| AC3 | No hint exceeds MAX | `test_no_batch_exceeds_max_tokens`, `test_large_single_chapter_split_mid_chapter`, `test_chapter_boundary_flush_when_merge_would_overflow`, `test_large_chapter_after_small_merged_chapters` |
| AC4 | `estimated_batch_count == len(hints)` | All tests (always asserted via `estimated_batch_count`) |
| AC5 | `chapter_boundaries` maps to first batch index | `test_chapter_boundaries_map_correct_on_merge`, `test_two_tiny_chapters_merged_into_one_batch`, `test_large_chapter_after_small_merged_chapters` |
| AC6 | `chapter_ref` = first segment's chapter | `test_batch_hint_chapter_ref_is_first_merged_chapter` |
| AC7 | 10 × 200-token chapters → 1 batch | `test_ten_tiny_chapters_merged_efficiently` |
| AC8 | 10 × 300-token chapters → batches ≤ MAX | `test_no_batch_exceeds_max_tokens` (50 × 100-token variant) |
| AC9 | Chapter > MAX still split correctly | `test_large_single_chapter_split_mid_chapter` |
| AC10 | Existing `TestBatchPlanning` tests pass | All 23 `test_pipeline_segmentation.py` tests pass ✅ |

Test name `test_target_and_max_from_module_constants_respected` differs from the plan's `test_target_and_max_from_env_respected`. The rename is more accurate: the test patches module-level constants (not env vars), so the name is an improvement over the plan spec.

---

## Security

No security concerns. Pure algorithmic code with no I/O, no external calls, no secrets, no filesystem operations.

---

## Required Changes

None.

---

## Suggested Improvements

- [optional] The first line of the module docstring (`Groups segments into chapter-scoped, token-bounded translation batches.`) could be updated to reflect cross-chapter merging, e.g. `Groups segments into token-bounded translation batches, merging short consecutive chapters to reduce API overhead.` Purely cosmetic; no functional impact.

---

## Next Step

Iteration Manager should transition COST-2 to `approved` and mark the task `completed` in `docs/TASKS.md`.

---

```json
{
  "handoff": {
    "agent": "Reviewer",
    "artifact_type": "code",
    "artifact_path": [
      "app/pipeline/segmentation/batch_planner.py",
      "tests/test_batch_planner.py"
    ],
    "status": "approved",
    "next_recommended_agent": null,
    "next_recommended_reason": null,
    "blocking_issues": [],
    "workflow_state": {
      "task_id": "COST-2",
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
