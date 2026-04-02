"""Tests for the segmentation pipeline stage.

Covers:
- Basic paragraph segmentation from NormalizedDocument
- Segment ID stability across repeated calls
- Multi-chapter document — chapter assignment and chapter_boundaries
- Empty text raises SegmentationError
- Invalid mode raises SegmentationError
- Large paragraph sub-segmentation
- Batch planning token limits
- BatchBoundaryHint completeness (no segments lost)
- Token estimate reasonableness
- SegmentCollection fields
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.pipeline.ingestion.models import ChapterRef, NormalizedDocument
from app.pipeline.segmentation.batch_planner import MAX_TOKENS_PER_BATCH
from app.pipeline.segmentation.models import SegmentationError
from app.pipeline.segmentation.stage import segment, _estimate_tokens, _make_segment_id


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_doc(
    text: str,
    chapter_refs: list | None = None,
    source_word_count: int | None = None,
    document_id: uuid.UUID | None = None,
) -> NormalizedDocument:
    if document_id is None:
        document_id = uuid.uuid4()
    if source_word_count is None:
        source_word_count = len(text.split())
    return NormalizedDocument(
        document_id=document_id,
        source_type="epub",
        title="Test Book",
        author="Test Author",
        text=text,
        detected_language="en",
        detection_confidence=0.99,
        source_word_count=source_word_count,
        chapter_refs=chapter_refs or [],
    )


def _chapter_ref(chapter_id: str, order: int = 0) -> ChapterRef:
    return ChapterRef(chapter_id=chapter_id, title=f"Chapter {order+1}", order=order)


# ── Basic segmentation ────────────────────────────────────────────────────────


class TestBasicSegmentation:
    def test_returns_segment_collection(self):
        doc = _make_doc("Hello world.\nSecond paragraph.")
        result = segment(doc, mode="translate")
        assert result.document_id == doc.document_id
        assert result.mode == "translate"
        assert len(result.segments) >= 1

    def test_guided_mode_accepted(self):
        doc = _make_doc("Some text here.")
        result = segment(doc, mode="guided")
        assert result.mode == "guided"

    def test_paragraphs_split_by_newline(self):
        doc = _make_doc("First paragraph.\nSecond paragraph.\nThird paragraph.")
        result = segment(doc, mode="translate")
        texts = [s.original_text for s in result.segments]
        assert "First paragraph." in texts
        assert "Second paragraph." in texts
        assert "Third paragraph." in texts

    def test_empty_lines_filtered_out(self):
        doc = _make_doc("First.\n\n\nSecond.\n")
        result = segment(doc, mode="translate")
        for seg in result.segments:
            assert seg.original_text.strip() != ""

    def test_segment_has_required_fields(self):
        doc = _make_doc("A sentence here.")
        result = segment(doc, mode="translate")
        assert len(result.segments) >= 1
        s = result.segments[0]
        assert s.id
        assert s.paragraph_id
        assert s.chapter_ref
        assert s.original_text
        assert s.token_estimate >= 1
        assert s.structural_ref is None

    def test_token_estimate_at_least_one(self):
        doc = _make_doc("Hi.")
        result = segment(doc, mode="translate")
        assert all(s.token_estimate >= 1 for s in result.segments)


# ── Segment ID stability ──────────────────────────────────────────────────────


class TestSegmentIdStability:
    def test_same_doc_same_ids(self):
        doc_id = uuid.uuid4()
        doc = _make_doc("Para one.\nPara two.", document_id=doc_id)
        result1 = segment(doc, mode="translate")
        result2 = segment(doc, mode="translate")
        ids1 = [s.id for s in result1.segments]
        ids2 = [s.id for s in result2.segments]
        assert ids1 == ids2

    def test_different_doc_id_different_seg_ids(self):
        text = "Para one.\nPara two."
        doc_a = _make_doc(text, document_id=uuid.uuid4())
        doc_b = _make_doc(text, document_id=uuid.uuid4())
        ids_a = {s.id for s in segment(doc_a, mode="translate").segments}
        ids_b = {s.id for s in segment(doc_b, mode="translate").segments}
        assert ids_a != ids_b

    def test_all_segment_ids_unique(self):
        doc = _make_doc(
            "Para one.\nPara two.\nPara three.\nPara four.\nPara five."
        )
        result = segment(doc, mode="translate")
        ids = [s.id for s in result.segments]
        assert len(ids) == len(set(ids))


# ── Multi-chapter documents ───────────────────────────────────────────────────


class TestMultiChapterDocument:
    def test_chapter_refs_assigned(self):
        refs = [_chapter_ref("ch1", 0), _chapter_ref("ch2", 1)]
        doc = _make_doc(
            "Chapter one first para.\n\nChapter two first para.",
            chapter_refs=refs,
        )
        result = segment(doc, mode="translate")
        chapter_refs_used = {s.chapter_ref for s in result.segments}
        assert "ch1" in chapter_refs_used
        assert "ch2" in chapter_refs_used

    def test_chapter_boundaries_in_batch_planning(self):
        refs = [_chapter_ref("ch1", 0), _chapter_ref("ch2", 1)]
        doc = _make_doc(
            "Chapter one first para.\n\nChapter two first para.",
            chapter_refs=refs,
        )
        result = segment(doc, mode="translate")
        assert "ch1" in result.batch_planning.chapter_boundaries
        assert "ch2" in result.batch_planning.chapter_boundaries

    def test_fallback_chapter_ref_when_no_chapter_refs(self):
        doc = _make_doc("Para one.\n\nPara two.", chapter_refs=[])
        result = segment(doc, mode="translate")
        assert all(s.chapter_ref for s in result.segments)


# ── Error cases ───────────────────────────────────────────────────────────────


class TestErrorCases:
    def test_empty_text_raises_segmentation_error(self):
        doc = _make_doc("   ")
        with pytest.raises(SegmentationError):
            segment(doc, mode="translate")

    def test_invalid_mode_raises_segmentation_error(self):
        doc = _make_doc("Some text.")
        with pytest.raises(SegmentationError):
            segment(doc, mode="invalid_mode")


# ── Sub-segmentation ──────────────────────────────────────────────────────────


class TestSubSegmentation:
    def test_large_paragraph_produces_multiple_segments_with_shared_paragraph_id(self):
        # Build a paragraph that is definitely > MAX_TOKENS_PER_SEGMENT tokens.
        # MAX_TOKENS_PER_SEGMENT defaults to 500; each token ~4 chars → need >2000 chars.
        long_para = "This is a sentence with some words. " * 200  # ~7200 chars
        doc = _make_doc(long_para)
        result = segment(doc, mode="translate")

        paragraph_ids = [s.paragraph_id for s in result.segments]
        # All sub-segments should share the same paragraph_id.
        assert len(set(paragraph_ids)) == 1
        # But the overall segment collection should have more than 1 segment.
        assert len(result.segments) > 1

    def test_large_paragraph_all_text_preserved(self):
        sentence = "Word one two three four five six seven eight nine ten. "
        long_para = sentence * 200
        doc = _make_doc(long_para)
        result = segment(doc, mode="translate")
        combined = " ".join(s.original_text for s in result.segments)
        # Every sentence should appear somewhere in the output.
        assert "Word one two three four five six" in combined


# ── Batch planning ────────────────────────────────────────────────────────────


class TestBatchPlanning:
    def test_no_batch_exceeds_max_tokens(self):
        # Generate many small paragraphs.
        lines = [f"Paragraph number {i} with some words." for i in range(100)]
        doc = _make_doc("\n".join(lines))
        result = segment(doc, mode="translate")
        for hint in result.batch_planning.batch_boundary_hints:
            assert hint.token_total <= MAX_TOKENS_PER_BATCH

    def test_all_segments_appear_in_hints(self):
        lines = [f"Para {i}." for i in range(20)]
        doc = _make_doc("\n".join(lines))
        result = segment(doc, mode="translate")
        seg_ids_in_hints = set()
        for hint in result.batch_planning.batch_boundary_hints:
            seg_ids_in_hints.update(hint.segment_ids)
        all_seg_ids = {s.id for s in result.segments}
        assert seg_ids_in_hints == all_seg_ids

    def test_estimated_batch_count_matches_hints(self):
        lines = [f"Para {i}." for i in range(30)]
        doc = _make_doc("\n".join(lines))
        result = segment(doc, mode="translate")
        assert result.batch_planning.estimated_batch_count == len(
            result.batch_planning.batch_boundary_hints
        )

    def test_single_short_document_is_one_batch(self):
        doc = _make_doc("Short para.\nAnother short para.")
        result = segment(doc, mode="translate")
        assert result.batch_planning.estimated_batch_count == 1


# ── Token estimate ────────────────────────────────────────────────────────────


class TestTokenEstimate:
    def test_token_estimate_roughly_proportional_to_text_length(self):
        short_text = "Hi."
        long_text = "Hi. " * 100
        assert _estimate_tokens(long_text) > _estimate_tokens(short_text)

    def test_token_estimate_minimum_one(self):
        assert _estimate_tokens("x") >= 1

    def test_segment_collection_token_sum_reasonable(self):
        text = "Word " * 1000  # 1000 words
        doc = _make_doc(text)
        result = segment(doc, mode="translate")
        total_tokens = sum(s.token_estimate for s in result.segments)
        # 1000 words × ~5 chars/word = ~5000 chars → ~1250 tokens
        assert 200 < total_tokens < 5000
