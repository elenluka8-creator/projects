"""Batch planner for the segmentation stage.

Groups segments into chapter-scoped, token-bounded translation batches.

Batch strategy (per DEC-005):
  1. Merge short consecutive chapters into one batch to reduce API call overhead.
  2. Flush at a chapter boundary only when the current batch is at or above
     TARGET_TOKENS_PER_BATCH, or when adding the entire next chapter would
     exceed MAX_TOKENS_PER_BATCH.
  3. If a single chapter exceeds MAX_TOKENS_PER_BATCH, split it mid-chapter.
  4. Never exceed MAX_TOKENS_PER_BATCH per batch.

All limits are configurable from environment variables with safe defaults.
"""
from __future__ import annotations

import os
from typing import Dict, List

from app.pipeline.segmentation.models import BatchBoundaryHint, BatchPlanning, Segment

# ── Configurable limits ───────────────────────────────────────────────────────

MAX_TOKENS_PER_SEGMENT: int = int(os.environ.get("MAX_TOKENS_PER_SEGMENT", "500"))
TARGET_TOKENS_PER_BATCH: int = int(os.environ.get("TARGET_TOKENS_PER_BATCH", "2000"))
MAX_TOKENS_PER_BATCH: int = int(os.environ.get("MAX_TOKENS_PER_BATCH", "4000"))


def plan_batches(segments: List[Segment]) -> BatchPlanning:
    """Group segments into translation batches and return BatchPlanning.

    Args:
        segments: Ordered list of segments produced by the segmentation stage.

    Returns:
        BatchPlanning with chapter_boundaries, batch_boundary_hints,
        and estimated_batch_count.
    """
    if not segments:
        return BatchPlanning(
            chapter_boundaries={},
            batch_boundary_hints=[],
            estimated_batch_count=0,
        )

    # Pre-scan: compute total token count per chapter for merge/flush decisions.
    chapter_token_totals: Dict[str, int] = {}
    for seg in segments:
        chapter_token_totals[seg.chapter_ref] = (
            chapter_token_totals.get(seg.chapter_ref, 0) + seg.token_estimate
        )

    hints: List[BatchBoundaryHint] = []
    chapter_boundaries: Dict[str, int] = {}

    current_ids: List[str] = []
    current_tokens: int = 0
    batch_first_chapter: str = segments[0].chapter_ref  # chapter_ref for the next hint
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
            current_chapter = seg.chapter_ref  # always advance chapter tracking
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

        # Record the first batch index for this chapter.
        if seg.chapter_ref not in chapter_boundaries:
            chapter_boundaries[seg.chapter_ref] = batch_index

        current_ids.append(seg.id)
        current_tokens += seg.token_estimate

    # Flush any remaining segments.
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
