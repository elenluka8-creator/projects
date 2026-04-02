"""Formatting stage entry point.

Single public function: format_document(collection) -> FormattedDocument

Responsibilities:
- Group translated segments by paragraph_id (preserving document order)
- Reconstruct sub-segmented paragraphs into single FormattedBlocks
- Apply mode-specific block structure (Translate or Guided)
- Return a deterministic FormattedDocument

This stage is purely deterministic — no LLMs, no network calls, no DB writes.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.logging.structured import log_structured
from app.pipeline.formatting.models import FormattedBlock, FormattedDocument, FormattingError
from app.pipeline.translation.models import TranslatedSegment, TranslatedSegmentCollection

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"translate", "guided"})


def format_document(collection: TranslatedSegmentCollection) -> FormattedDocument:
    """Convert a TranslatedSegmentCollection into a FormattedDocument.

    Groups segments by paragraph_id and reconstructs sub-segmented paragraphs
    into single FormattedBlocks. Block order follows the first occurrence of
    each paragraph_id in the translated_segments list, preserving document order.

    Translate Mode: one block per paragraph with translation only.
    Guided Mode: one block per paragraph with original, translation, explanations,
    and original_repeat (4-block reading structure).

    Args:
        collection: Output of the translation stage.

    Returns:
        FormattedDocument with one FormattedBlock per unique paragraph_id.

    Raises:
        FormattingError: If the collection has no segments or an unsupported mode.
    """
    if collection.mode not in _VALID_MODES:
        raise FormattingError(
            f"Unsupported mode '{collection.mode}'. Must be one of: {sorted(_VALID_MODES)}"
        )
    if not collection.translated_segments:
        raise FormattingError(
            f"TranslatedSegmentCollection for document {collection.document_id} "
            "has no translated segments."
        )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="formatting_started",
        payload={
            "document_id": str(collection.document_id),
            "mode": collection.mode,
            "segment_count": len(collection.translated_segments),
        },
    )

    # Build ordered groups: paragraph_id → [TranslatedSegment, ...]
    # The insertion-order of the dict preserves first-occurrence ordering.
    groups: Dict[str, List[TranslatedSegment]] = {}
    for seg in collection.translated_segments:
        if seg.paragraph_id not in groups:
            groups[seg.paragraph_id] = []
        groups[seg.paragraph_id].append(seg)

    formatted_blocks = [
        _build_block(paragraph_id, segs, collection.mode)
        for paragraph_id, segs in groups.items()
    ]

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="formatting_completed",
        payload={
            "document_id": str(collection.document_id),
            "block_count": len(formatted_blocks),
        },
    )

    return FormattedDocument(
        document_id=collection.document_id,
        mode=collection.mode,
        formatted_blocks=formatted_blocks,
    )


def _build_block(
    paragraph_id: str,
    segments: List[TranslatedSegment],
    mode: str,
) -> FormattedBlock:
    """Build one FormattedBlock from one or more segments sharing a paragraph_id.

    Sub-segments are joined with a single space to reconstruct the full paragraph.
    Explanations are deduplicated while preserving first-seen order.
    """
    original = " ".join(s.original_text for s in segments)
    translation = " ".join(s.translated_text for s in segments)
    chapter_ref = segments[0].chapter_ref

    if mode == "guided":
        explanations = _merge_explanations(segments)
        original_repeat: Optional[str] = original
    else:
        explanations = []
        original_repeat = None

    return FormattedBlock(
        paragraph_id=paragraph_id,
        chapter_ref=chapter_ref,
        original=original,
        translation=translation,
        explanations=explanations,
        original_repeat=original_repeat,
    )


def _merge_explanations(segments: List[TranslatedSegment]) -> List[str]:
    """Merge explanation lists from multiple sub-segments, deduplicating entries
    while preserving the order of first occurrence."""
    seen: set = set()
    merged: List[str] = []
    for seg in segments:
        for note in seg.explanations:
            if note not in seen:
                seen.add(note)
                merged.append(note)
    return merged
