"""Formatting stage data models.

Implements the pipeline contract from docs/PIPELINE_CONTRACTS.md §4 Formatting.
All types are frozen dataclasses — callers must not mutate them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class FormattedBlock:
    """A single paragraph-level block in the formatted output.

    Contract fields per PIPELINE_CONTRACTS.md §4:
        paragraph_id    -- Stable identifier matching the source Segment paragraph_id.
                           One FormattedBlock is produced per unique paragraph_id,
                           regardless of how many sub-segments the paragraph was split
                           into during segmentation.
        chapter_ref     -- Chapter identifier from the source Segment.
        original        -- Full reconstructed original text for this paragraph.
                           For sub-segmented paragraphs this is the joined text of all
                           sub-segments (space-separated) in document order.
        translation     -- Full reconstructed translation for this paragraph.
                           Joined from sub-segment translations in the same order.
        explanations    -- Cultural/idiomatic notes (Guided Mode only; empty list in
                           Translate Mode). Union of all sub-segment explanation lists,
                           deduplicated while preserving first-seen order.
        original_repeat -- Equal to `original` in Guided Mode (shown again at the end
                           of the 4-block structure). None in Translate Mode.
                           For sub-segmented paragraphs this is the same joined original
                           text as `original`.
    """

    paragraph_id: str
    chapter_ref: str
    original: str
    translation: str
    explanations: List[str]
    original_repeat: Optional[str]


@dataclass(frozen=True)
class FormattedDocument:
    """The output of the formatting stage.

    Contract fields per PIPELINE_CONTRACTS.md §4:
        document_id      -- From the source TranslatedSegmentCollection.
        mode             -- "translate" or "guided".
        formatted_blocks -- Ordered list of FormattedBlock (paragraph order across all
                            chapters, matching the order of the source document).
    """

    document_id: uuid.UUID
    mode: str
    formatted_blocks: List[FormattedBlock]


class FormattingError(Exception):
    """Base class for all formatting stage errors."""
