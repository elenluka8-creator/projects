"""Segmentation stage entry point.

Single public function: segment(document, mode) -> SegmentCollection

Responsibilities:
- Validate mode and document text
- Split full text into chapter groups (separated by double-newlines)
- Within each chapter group, split into paragraphs (single-newline separated)
- Sub-segment paragraphs that exceed MAX_TOKENS_PER_SEGMENT at sentence boundaries
- Assign deterministic stable segment IDs (sha256 hash per DEC-009)
- Estimate token counts using the len(text)//4 heuristic
- Delegate batch planning to BatchPlanner
- Emit structured log events

Out of scope: DB writes, LLM calls, translation, formatting.

Chapter assignment note (MVP limitation):
    NormalizedDocument.text is a flat string with chapters joined by \\n\\n.
    Chapter groups are identified by splitting on \\n\\n; each group at index i
    is matched to chapter_refs[i] when available. Because the ingestion stage
    excludes empty chapters from the text (but includes them in chapter_refs),
    this mapping may drift when empty chapters precede non-empty ones.
    A future ingestion contract extension (per-chapter text list) would fix this.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import List, Optional, Tuple

from app.config.policy import VALID_MODES
from app.logging.structured import log_structured
from app.pipeline.ingestion.models import ChapterRef, NormalizedDocument
from app.pipeline.segmentation.batch_planner import MAX_TOKENS_PER_SEGMENT, plan_batches
from app.pipeline.segmentation.models import (
    Segment,
    SegmentCollection,
    SegmentationError,
)

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def segment(document: NormalizedDocument, mode: str) -> SegmentCollection:
    """Run the segmentation stage for a normalized document.

    Args:
        document: Output of the ingestion stage.
        mode:     Job mode — "translate" or "guided".

    Returns:
        SegmentCollection — the ordered segment list with batch-planning metadata.

    Raises:
        SegmentationError: Invalid mode or empty document text.
    """
    if mode not in VALID_MODES:
        raise SegmentationError(
            f"Invalid mode '{mode}'. Allowed: {', '.join(sorted(VALID_MODES))}."
        )
    if not document.text or not document.text.strip():
        raise SegmentationError(
            f"Document {document.document_id} has no extractable text."
        )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="segmentation_started",
        payload={
            "document_id": str(document.document_id),
            "mode": mode,
            "source_word_count": document.source_word_count,
            "chapter_count": len(document.chapter_refs),
        },
    )

    segments = _build_segments(document)
    batch_planning = plan_batches(segments)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="segmentation_completed",
        payload={
            "document_id": str(document.document_id),
            "segment_count": len(segments),
            "batch_count": batch_planning.estimated_batch_count,
        },
    )

    return SegmentCollection(
        document_id=document.document_id,
        mode=mode,
        segments=segments,
        batch_planning=batch_planning,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_segments(document: NormalizedDocument) -> List[Segment]:
    """Parse document text into an ordered list of Segment objects."""
    chapter_groups = document.text.split("\n\n")
    segments: List[Segment] = []

    for group_idx, group_text in enumerate(chapter_groups):
        group_text = group_text.strip()
        if not group_text:
            continue

        chapter_ref = _resolve_chapter_ref(document.chapter_refs, group_idx)

        para_idx = 0
        for line in group_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            paragraph_id = _make_segment_id(document.document_id, chapter_ref, para_idx)
            token_est = _estimate_tokens(line)

            if token_est > MAX_TOKENS_PER_SEGMENT:
                sub_segs = _sub_segment(
                    document.document_id, chapter_ref, para_idx, paragraph_id, line
                )
                segments.extend(sub_segs)
            else:
                segments.append(
                    Segment(
                        id=paragraph_id,
                        paragraph_id=paragraph_id,
                        chapter_ref=chapter_ref,
                        structural_ref=None,
                        original_text=line,
                        token_estimate=token_est,
                    )
                )

            para_idx += 1

    return segments


def _resolve_chapter_ref(chapter_refs: List[ChapterRef], group_idx: int) -> str:
    """Return a chapter_id for the given text-chunk index.

    When chapter_refs is available, use chapter_refs[group_idx].chapter_id.
    Falls back to a synthetic identifier when the index is out of range.
    """
    if chapter_refs and group_idx < len(chapter_refs):
        return chapter_refs[group_idx].chapter_id
    return f"chunk_{group_idx}"


def _sub_segment(
    document_id: uuid.UUID,
    chapter_ref: str,
    para_idx: int,
    paragraph_id: str,
    text: str,
) -> List[Segment]:
    """Split an oversized paragraph into sentence-bounded sub-segments."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        sentences = [text]

    result: List[Segment] = []
    bucket: List[str] = []
    bucket_tokens: int = 0
    sub_idx: int = 0

    for sentence in sentences:
        s_tokens = _estimate_tokens(sentence)
        if bucket and bucket_tokens + s_tokens > MAX_TOKENS_PER_SEGMENT:
            result.append(
                _make_sub_segment(
                    document_id, chapter_ref, para_idx, sub_idx,
                    paragraph_id, " ".join(bucket), bucket_tokens,
                )
            )
            sub_idx += 1
            bucket = []
            bucket_tokens = 0
        bucket.append(sentence)
        bucket_tokens += s_tokens

    if bucket:
        result.append(
            _make_sub_segment(
                document_id, chapter_ref, para_idx, sub_idx,
                paragraph_id, " ".join(bucket), bucket_tokens,
            )
        )

    return result if result else [
        Segment(
            id=paragraph_id,
            paragraph_id=paragraph_id,
            chapter_ref=chapter_ref,
            structural_ref=None,
            original_text=text,
            token_estimate=_estimate_tokens(text),
        )
    ]


def _make_sub_segment(
    document_id: uuid.UUID,
    chapter_ref: str,
    para_idx: int,
    sub_idx: int,
    paragraph_id: str,
    text: str,
    token_estimate: int,
) -> Segment:
    seg_id = _make_segment_id(document_id, chapter_ref, para_idx, sub_idx)
    return Segment(
        id=seg_id,
        paragraph_id=paragraph_id,
        chapter_ref=chapter_ref,
        structural_ref=None,
        original_text=text,
        token_estimate=token_estimate,
    )


def _make_segment_id(
    document_id: uuid.UUID,
    chapter_ref: str,
    para_idx: int,
    sub_idx: Optional[int] = None,
) -> str:
    """Compute a deterministic, stable segment identifier (DEC-009)."""
    if sub_idx is None:
        key = f"{document_id}:{chapter_ref}:{para_idx}"
    else:
        key = f"{document_id}:{chapter_ref}:{para_idx}:{sub_idx}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _estimate_tokens(text: str) -> int:
    """Approximate token count using the characters-divided-by-4 heuristic.

    Reasonable for Latin, Cyrillic, and CJK mixed content.
    Minimum 1 to avoid zero estimates for very short strings.
    """
    return max(1, len(text) // 4)
