"""Tests for app.pipeline.formatting.

Covers both Translate Mode and Guided Mode, sub-segment reconstruction,
chapter structure preservation, paragraph ordering, and error cases.
All tests are deterministic — no mocks, no I/O.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import pytest

from app.pipeline.formatting.models import FormattedBlock, FormattedDocument, FormattingError
from app.pipeline.formatting.stage import format_document, _merge_explanations
from app.pipeline.translation.models import TranslatedSegment, TranslatedSegmentCollection


# ── Helpers ────────────────────────────────────────────────────────────────


def _seg(
    seg_id: str,
    paragraph_id: str,
    original: str,
    translated: str,
    chapter_ref: str = "ch-1",
    explanations: Optional[List[str]] = None,
) -> TranslatedSegment:
    return TranslatedSegment(
        id=seg_id,
        paragraph_id=paragraph_id,
        chapter_ref=chapter_ref,
        structural_ref=None,
        original_text=original,
        translated_text=translated,
        explanations=explanations or [],
    )


def _collection(
    segments: List[TranslatedSegment],
    mode: str = "translate",
) -> TranslatedSegmentCollection:
    return TranslatedSegmentCollection(
        document_id=uuid.uuid4(),
        mode=mode,
        translated_segments=segments,
    )


# ── Translate Mode ─────────────────────────────────────────────────────────


class TestTranslateMode:

    def test_single_segment_produces_one_block(self):
        col = _collection([_seg("s1", "p1", "Bonjour", "Hello")])
        doc = format_document(col)
        assert len(doc.formatted_blocks) == 1

    def test_block_contains_original_and_translation(self):
        col = _collection([_seg("s1", "p1", "Bonjour", "Hello")])
        block = format_document(col).formatted_blocks[0]
        assert block.original == "Bonjour"
        assert block.translation == "Hello"

    def test_translate_mode_no_explanations(self):
        col = _collection([_seg("s1", "p1", "Bonjour", "Hello", explanations=["note"])])
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == []

    def test_translate_mode_original_repeat_is_none(self):
        col = _collection([_seg("s1", "p1", "Bonjour", "Hello")])
        block = format_document(col).formatted_blocks[0]
        assert block.original_repeat is None

    def test_paragraph_id_and_chapter_ref_preserved(self):
        col = _collection([_seg("s1", "para-42", "Text", "Texte", chapter_ref="ch-3")])
        block = format_document(col).formatted_blocks[0]
        assert block.paragraph_id == "para-42"
        assert block.chapter_ref == "ch-3"

    def test_multiple_segments_produce_multiple_blocks(self):
        segs = [_seg(f"s{i}", f"p{i}", f"Original {i}", f"Trans {i}") for i in range(5)]
        doc = format_document(_collection(segs))
        assert len(doc.formatted_blocks) == 5

    def test_block_order_matches_segment_order(self):
        segs = [_seg(f"s{i}", f"p{i}", f"O{i}", f"T{i}") for i in range(4)]
        blocks = format_document(_collection(segs)).formatted_blocks
        for i, block in enumerate(blocks):
            assert block.paragraph_id == f"p{i}"

    def test_document_id_and_mode_propagated(self):
        col = _collection([_seg("s1", "p1", "O", "T")])
        doc = format_document(col)
        assert doc.document_id == col.document_id
        assert doc.mode == "translate"


# ── Guided Mode ────────────────────────────────────────────────────────────


class TestGuidedMode:

    def test_guided_mode_block_has_all_four_fields(self):
        segs = [_seg("s1", "p1", "Il était une fois", "Once upon a time",
                     explanations=["French: 'Once upon a time'"])]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.original == "Il était une fois"
        assert block.translation == "Once upon a time"
        assert block.explanations == ["French: 'Once upon a time'"]
        assert block.original_repeat == "Il était une fois"

    def test_guided_mode_original_repeat_equals_original(self):
        segs = [_seg("s1", "p1", "Texto original", "Original text")]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.original_repeat == block.original

    def test_guided_mode_empty_explanations_allowed(self):
        segs = [_seg("s1", "p1", "Simple sentence", "Einfacher Satz")]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == []
        assert block.original_repeat is not None

    def test_guided_mode_multiple_explanations_preserved(self):
        segs = [_seg("s1", "p1", "O", "T",
                     explanations=["Note A", "Note B", "Note C"])]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == ["Note A", "Note B", "Note C"]


# ── Sub-segment reconstruction ─────────────────────────────────────────────


class TestSubSegmentReconstruction:

    def test_two_subsegments_merged_into_one_block(self):
        segs = [
            _seg("s1a", "p1", "First sentence.", "Première phrase."),
            _seg("s1b", "p1", "Second sentence.", "Deuxième phrase."),
        ]
        doc = format_document(_collection(segs))
        assert len(doc.formatted_blocks) == 1

    def test_merged_original_is_space_joined(self):
        segs = [
            _seg("s1a", "p1", "Hello", "Bonjour"),
            _seg("s1b", "p1", "world.", "monde."),
        ]
        block = format_document(_collection(segs)).formatted_blocks[0]
        assert block.original == "Hello world."

    def test_merged_translation_is_space_joined(self):
        segs = [
            _seg("s1a", "p1", "Hello", "Bonjour"),
            _seg("s1b", "p1", "world.", "monde."),
        ]
        block = format_document(_collection(segs)).formatted_blocks[0]
        assert block.translation == "Bonjour monde."

    def test_guided_merged_original_repeat_equals_merged_original(self):
        segs = [
            _seg("s1a", "p1", "First.", "Premier."),
            _seg("s1b", "p1", "Second.", "Deuxième."),
        ]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.original_repeat == block.original == "First. Second."

    def test_mixed_segments_and_single_segments(self):
        segs = [
            _seg("s1a", "p1", "A", "a"),
            _seg("s1b", "p1", "B", "b"),
            _seg("s2",  "p2", "C", "c"),
            _seg("s3a", "p3", "D", "d"),
            _seg("s3b", "p3", "E", "e"),
        ]
        doc = format_document(_collection(segs))
        assert len(doc.formatted_blocks) == 3
        assert doc.formatted_blocks[0].original == "A B"
        assert doc.formatted_blocks[1].original == "C"
        assert doc.formatted_blocks[2].original == "D E"

    def test_subsegment_chapter_ref_taken_from_first(self):
        segs = [
            _seg("s1a", "p1", "A", "a", chapter_ref="ch-2"),
            _seg("s1b", "p1", "B", "b", chapter_ref="ch-2"),
        ]
        block = format_document(_collection(segs)).formatted_blocks[0]
        assert block.chapter_ref == "ch-2"


# ── Explanation merging ────────────────────────────────────────────────────


class TestExplanationMerging:

    def test_explanations_merged_across_subsegments(self):
        segs = [
            _seg("s1a", "p1", "A", "a", explanations=["Note 1"]),
            _seg("s1b", "p1", "B", "b", explanations=["Note 2"]),
        ]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == ["Note 1", "Note 2"]

    def test_duplicate_explanations_deduplicated(self):
        segs = [
            _seg("s1a", "p1", "A", "a", explanations=["Idiom: X"]),
            _seg("s1b", "p1", "B", "b", explanations=["Idiom: X", "Cultural note"]),
        ]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == ["Idiom: X", "Cultural note"]

    def test_merge_explanations_preserves_order(self):
        segs = [
            _seg("s1a", "p1", "A", "a", explanations=["first", "second"]),
            _seg("s1b", "p1", "B", "b", explanations=["third"]),
        ]
        col = _collection(segs, mode="guided")
        block = format_document(col).formatted_blocks[0]
        assert block.explanations == ["first", "second", "third"]

    def test_merge_explanations_helper_deduplication(self):
        segs = [
            _seg("s1", "p1", "A", "a", explanations=["x", "y"]),
            _seg("s2", "p1", "B", "b", explanations=["y", "z"]),
        ]
        result = _merge_explanations(segs)
        assert result == ["x", "y", "z"]


# ── Chapter structure ──────────────────────────────────────────────────────


class TestChapterStructure:

    def test_blocks_from_different_chapters_preserved(self):
        segs = [
            _seg("s1", "p1", "Ch1 para1", "T1", chapter_ref="ch-1"),
            _seg("s2", "p2", "Ch2 para1", "T2", chapter_ref="ch-2"),
            _seg("s3", "p3", "Ch2 para2", "T3", chapter_ref="ch-2"),
        ]
        doc = format_document(_collection(segs))
        assert len(doc.formatted_blocks) == 3
        assert doc.formatted_blocks[0].chapter_ref == "ch-1"
        assert doc.formatted_blocks[1].chapter_ref == "ch-2"
        assert doc.formatted_blocks[2].chapter_ref == "ch-2"

    def test_block_order_preserved_across_chapters(self):
        segs = [
            _seg("s1", "p1", "A", "a", chapter_ref="ch-1"),
            _seg("s2", "p2", "B", "b", chapter_ref="ch-2"),
            _seg("s3", "p3", "C", "c", chapter_ref="ch-3"),
        ]
        blocks = format_document(_collection(segs)).formatted_blocks
        assert [b.chapter_ref for b in blocks] == ["ch-1", "ch-2", "ch-3"]


# ── Determinism ────────────────────────────────────────────────────────────


class TestDeterminism:

    def test_same_input_produces_identical_output(self):
        segs = [_seg(f"s{i}", f"p{i}", f"Original {i}", f"Trans {i}") for i in range(6)]
        col = _collection(segs)
        result1 = format_document(col)
        result2 = format_document(col)
        assert result1.formatted_blocks == result2.formatted_blocks

    def test_guided_same_input_produces_identical_output(self):
        segs = [
            _seg("s1", "p1", "Text", "Texte", explanations=["Note"]),
        ]
        col = _collection(segs, mode="guided")
        assert format_document(col).formatted_blocks == format_document(col).formatted_blocks


# ── Error cases ────────────────────────────────────────────────────────────


class TestErrorCases:

    def test_empty_segments_raises_formatting_error(self):
        col = TranslatedSegmentCollection(
            document_id=uuid.uuid4(),
            mode="translate",
            translated_segments=[],
        )
        with pytest.raises(FormattingError, match="no translated segments"):
            format_document(col)

    def test_invalid_mode_raises_formatting_error(self):
        col = TranslatedSegmentCollection(
            document_id=uuid.uuid4(),
            mode="unknown",
            translated_segments=[_seg("s1", "p1", "O", "T")],
        )
        with pytest.raises(FormattingError, match="Unsupported mode"):
            format_document(col)
