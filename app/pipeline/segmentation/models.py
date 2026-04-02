"""Segmentation stage data models.

Implements the pipeline contract from docs/PIPELINE_CONTRACTS.md §2 Segmentation.
All types are frozen dataclasses — callers must not mutate them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Segment:
    """A paragraph-visible processing unit produced by the segmentation stage.

    Contract fields per PIPELINE_CONTRACTS.md §2:
        id              -- Deterministic stable identifier.
                           Formula: sha256(document_id:chapter_ref:para_idx)[:16]
                           For sub-segments: sha256(document_id:chapter_ref:para_idx:sub_idx)[:16]
        paragraph_id    -- Stable identifier for the source paragraph.
                           Equal to id for unsplit paragraphs; shared across all sub-segments
                           of the same paragraph so the formatting stage can reconstruct it.
        chapter_ref     -- chapter_id of the chapter this segment belongs to.
                           MVP: derived from NormalizedDocument.chapter_refs by chunk index.
        structural_ref  -- None for text paragraphs (reserved for structural element context).
        original_text   -- The raw paragraph (or sub-segment) text.
        token_estimate  -- Approximate token count for batch planning (len(text)//4 heuristic).
    """

    id: str
    paragraph_id: str
    chapter_ref: str
    structural_ref: Optional[str]
    original_text: str
    token_estimate: int


@dataclass(frozen=True)
class BatchBoundaryHint:
    """Describes one proposed translation batch for orchestration planning."""

    batch_index: int
    segment_ids: List[str]
    token_total: int
    chapter_ref: str  # chapter_ref of the first segment in this batch


@dataclass(frozen=True)
class BatchPlanning:
    """Batch-planning metadata for translation orchestration.

    Contract fields per PIPELINE_CONTRACTS.md §2:
        chapter_boundaries    -- {chapter_ref: batch_index} mapping the first batch
                                 index where each chapter's segments appear.
        batch_boundary_hints  -- Ordered list of BatchBoundaryHint (one per batch).
        estimated_batch_count -- Total number of proposed batches.
    """

    chapter_boundaries: Dict[str, int]
    batch_boundary_hints: List[BatchBoundaryHint]
    estimated_batch_count: int


@dataclass(frozen=True)
class SegmentCollection:
    """The output of the segmentation stage.

    Contract fields per PIPELINE_CONTRACTS.md §2:
        document_id    -- From the source NormalizedDocument.
        mode           -- "translate" or "guided" (propagated from job config).
        segments       -- Ordered list of Segment (paragraph order across all chapters).
        batch_planning -- Batch-planning metadata for the translation stage.
    """

    document_id: uuid.UUID
    mode: str
    segments: List[Segment]
    batch_planning: BatchPlanning


class SegmentationError(Exception):
    """Base class for all segmentation stage errors."""
