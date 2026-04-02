"""Unit tests for plan_batches() in the batch_planner module.

Tests cover:
- Empty input
- Single chapter below / at target
- Two small chapters merged into one batch
- Flush at chapter boundary when current batch is at TARGET
- Flush at chapter boundary when merging would overflow MAX
- Mid-chapter split when a chapter exceeds MAX
- chapter_boundaries correctness after merging
- BatchBoundaryHint.chapter_ref is the first chapter in the merged batch
- No batch exceeds MAX_TOKENS_PER_BATCH
- All segment IDs appear in exactly one hint
- MODULE-level TARGET / MAX constants respected when patched
"""
from __future__ import annotations

from typing import List

import pytest

import app.pipeline.segmentation.batch_planner as batch_planner_module
from app.pipeline.segmentation.batch_planner import plan_batches
from app.pipeline.segmentation.models import Segment


# ── Helper ────────────────────────────────────────────────────────────────────


def _seg(id: str, chapter_ref: str, token_estimate: int) -> Segment:
    return Segment(
        id=id,
        paragraph_id=id,
        chapter_ref=chapter_ref,
        structural_ref=None,
        original_text="x",
        token_estimate=token_estimate,
    )


def _segs_for_chapter(chapter_ref: str, token_estimate: int, count: int, id_prefix: str = "") -> List[Segment]:
    prefix = id_prefix or chapter_ref
    return [_seg(f"{prefix}_{i}", chapter_ref, token_estimate) for i in range(count)]


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestBatchPlannerEdgeCases:
    def test_empty_segments_returns_empty_planning(self):
        result = plan_batches([])
        assert result.chapter_boundaries == {}
        assert result.batch_boundary_hints == []
        assert result.estimated_batch_count == 0

    def test_single_segment_single_batch(self):
        segs = [_seg("s1", "ch1", 100)]
        result = plan_batches(segs)
        assert result.estimated_batch_count == 1
        assert len(result.batch_boundary_hints) == 1
        assert result.batch_boundary_hints[0].segment_ids == ["s1"]

    def test_no_batch_exceeds_max_tokens(self):
        # 50 chapters × 100 tokens each
        segs = []
        for i in range(50):
            segs.append(_seg(f"ch{i}_s0", f"ch{i}", 100))
        result = plan_batches(segs)
        max_tok = batch_planner_module.MAX_TOKENS_PER_BATCH
        for hint in result.batch_boundary_hints:
            assert hint.token_total <= max_tok

    def test_all_segments_appear_exactly_once(self):
        # Mix of large and small chapters
        segs = []
        for i in range(5):
            segs += _segs_for_chapter(f"small_{i}", 200, 2)
        segs += _segs_for_chapter("big", 1000, 5)
        result = plan_batches(segs)
        found: dict[str, int] = {}
        for hint in result.batch_boundary_hints:
            for sid in hint.segment_ids:
                found[sid] = found.get(sid, 0) + 1
        all_ids = {s.id for s in segs}
        assert set(found.keys()) == all_ids
        assert all(v == 1 for v in found.values())

    def test_target_and_max_from_module_constants_respected(self, monkeypatch):
        # With TARGET=500 and MAX=1000, three chapters of 600 tokens each
        # must each become their own batch (600 >= TARGET triggers flush at boundary).
        monkeypatch.setattr(batch_planner_module, "TARGET_TOKENS_PER_BATCH", 500)
        monkeypatch.setattr(batch_planner_module, "MAX_TOKENS_PER_BATCH", 1000)
        segs = []
        for ch in ("A", "B", "C"):
            segs.append(_seg(f"{ch}_s0", ch, 600))
        result = plan_batches(segs)
        assert result.estimated_batch_count == 3


# ── Merge small chapters ───────────────────────────────────────────────────────


class TestBatchPlannerMergeSmallChapters:
    def test_two_tiny_chapters_merged_into_one_batch(self):
        segs = [_seg("A_s0", "A", 200), _seg("B_s0", "B", 200)]
        result = plan_batches(segs)
        assert result.estimated_batch_count == 1
        assert result.chapter_boundaries["A"] == 0
        assert result.chapter_boundaries["B"] == 0

    def test_ten_tiny_chapters_merged_efficiently(self):
        segs = []
        for i in range(10):
            segs.append(_seg(f"ch{i}_s0", f"ch{i}", 200))
        result = plan_batches(segs)
        # 10 × 200 = 2000 total; all fit within MAX=4000
        assert result.estimated_batch_count == 1

    def test_chapter_boundary_flush_when_at_target(self):
        # Chapter A = 2000 tokens (at TARGET), then Chapter B = 200 tokens
        segs = _segs_for_chapter("A", 500, 4)  # 4 × 500 = 2000
        segs += [_seg("B_s0", "B", 200)]
        result = plan_batches(segs)
        assert result.estimated_batch_count == 2
        assert result.chapter_boundaries["B"] == 1

    def test_chapter_boundary_flush_when_merge_would_overflow(self):
        # Chapter A has 1800 tokens (below TARGET=2000, so no at_target flush).
        # Chapter B has 2500 tokens → 1800+2500=4300 > MAX=4000 → flush before B.
        segs = _segs_for_chapter("A", 900, 2)   # 2 × 900 = 1800 tokens
        segs += _segs_for_chapter("B", 500, 5)  # 5 × 500 = 2500 tokens
        result = plan_batches(segs)
        # A and B must be in different batches
        assert result.chapter_boundaries["A"] != result.chapter_boundaries["B"]
        # No batch should exceed MAX
        max_tok = batch_planner_module.MAX_TOKENS_PER_BATCH
        for hint in result.batch_boundary_hints:
            assert hint.token_total <= max_tok

    def test_chapter_boundaries_map_correct_on_merge(self):
        # A (1000) + B (1000) → merge into batch 0 (total 2000 = TARGET).
        # At C's boundary: at_target=True → flush. C lands in batch 1.
        segs = _segs_for_chapter("A", 500, 2)   # 2 × 500 = 1000
        segs += _segs_for_chapter("B", 500, 2)  # 2 × 500 = 1000; 1000+1000=2000
        segs += _segs_for_chapter("C", 500, 4)  # 4 × 500 = 2000 → flush before C
        result = plan_batches(segs)
        assert result.chapter_boundaries["A"] == 0
        assert result.chapter_boundaries["B"] == 0
        assert result.chapter_boundaries["C"] == 1

    def test_batch_hint_chapter_ref_is_first_merged_chapter(self):
        segs = [_seg("A_s0", "A", 100), _seg("B_s0", "B", 100)]
        result = plan_batches(segs)
        assert result.batch_boundary_hints[0].chapter_ref == "A"


# ── Mid-chapter split ──────────────────────────────────────────────────────────


class TestBatchPlannerMidChapterSplit:
    def test_large_single_chapter_split_mid_chapter(self):
        # 1 chapter, 5 × 1000 = 5000 tokens total (MAX=4000) → ≥2 batches
        segs = _segs_for_chapter("big", 1000, 5)
        result = plan_batches(segs)
        assert result.estimated_batch_count >= 2
        # No batch exceeds MAX
        max_tok = batch_planner_module.MAX_TOKENS_PER_BATCH
        for hint in result.batch_boundary_hints:
            assert hint.token_total <= max_tok
        # All segment IDs present
        all_ids = {s.id for s in segs}
        found_ids: set[str] = set()
        for hint in result.batch_boundary_hints:
            found_ids.update(hint.segment_ids)
        assert found_ids == all_ids

    def test_large_chapter_after_small_merged_chapters(self):
        # A+B (100 tokens each, merged) → batch 0
        # C (5 × 1000 = 5000 tokens, split across multiple batches)
        segs = [_seg("A_s0", "A", 100), _seg("B_s0", "B", 100)]
        segs += _segs_for_chapter("C", 1000, 5)
        result = plan_batches(segs)
        # A and B are in batch 0
        assert result.chapter_boundaries["A"] == 0
        assert result.chapter_boundaries["B"] == 0
        # C starts after the A+B batch
        c_batch = result.chapter_boundaries["C"]
        assert c_batch >= 1
        # All segments are accounted for
        all_ids = {s.id for s in segs}
        found_ids: set[str] = set()
        for hint in result.batch_boundary_hints:
            found_ids.update(hint.segment_ids)
        assert found_ids == all_ids
        # No batch exceeds MAX
        max_tok = batch_planner_module.MAX_TOKENS_PER_BATCH
        for hint in result.batch_boundary_hints:
            assert hint.token_total <= max_tok
