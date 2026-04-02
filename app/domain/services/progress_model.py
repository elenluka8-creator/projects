"""Stage-weighted progress and ETA helpers for durable job progress (DEC-010).

Weights sum to 100: ingest 5%, segment 10%, translate 70%, format 10%, export 5%.
"""
from __future__ import annotations

from typing import Final, Optional

_STAGE_ORDER: Final[tuple[str, ...]] = (
    "ingest",
    "segment",
    "translate",
    "format",
    "export",
)

_CUMULATIVE_AFTER: Final[dict[str, int]] = {
    "ingest": 5,
    "segment": 15,
    "translate": 85,
    "format": 95,
    "export": 100,
}


def cumulative_percent_after_stage(stage: str) -> int:
    """Return overall progress percent once `stage` has fully completed."""
    return _CUMULATIVE_AFTER.get(stage, 0)


def translate_progress_percent(batch_index: int, total_batches: int) -> int:
    """Progress percent after completing batch `batch_index` (0-based)."""
    if total_batches <= 0:
        return _CUMULATIVE_AFTER["segment"]
    done = min(batch_index + 1, total_batches)
    frac = done / total_batches
    return min(85, 15 + int(round(70 * frac)))


def compute_eta_seconds(
    elapsed_seconds: float,
    progress_percent: int,
    *,
    max_seconds: int = 86400,
) -> Optional[int]:
    """ETA from elapsed time and linear extrapolation. None if no signal yet."""
    if progress_percent <= 0 or elapsed_seconds <= 0:
        return None
    remaining = elapsed_seconds * (100.0 - progress_percent) / float(progress_percent)
    eta = int(max(0, round(remaining)))
    return min(eta, max_seconds)
