"""Non-LLM translation quality checks (DEC-005).

All checks are non-fatal — issues are returned as structured QualityIssue
objects and logged as warnings by the caller. No exception is raised here.

Checks implemented:
- untranslated_segment: translated text identical to original when languages differ
- short_translation:    translation suspiciously shorter than original (< 20%)
- hallucinated_paragraph: translation suspiciously longer than original (> 500%)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.pipeline.segmentation.models import Segment
from app.pipeline.translation.models import TranslatedSegment


@dataclass(frozen=True)
class QualityIssue:
    """Structured quality warning produced by a non-LLM check."""

    segment_id: str
    check_name: str
    message: str


def check_batch_quality(
    segments: List[Segment],
    translated: List[TranslatedSegment],
    source_lang: str,
    target_lang: str,
) -> List[QualityIssue]:
    """Run all quality checks for one translation batch.

    Args:
        segments:    Original segments for this batch.
        translated:  Translated segments returned by the provider.
        source_lang: BCP-47 source language code.
        target_lang: BCP-47 target language code.

    Returns:
        List of QualityIssue objects (empty when no issues found).
    """
    seg_map: Dict[str, Segment] = {s.id: s for s in segments}
    issues: List[QualityIssue] = []

    for ts in translated:
        orig = seg_map.get(ts.id)
        if orig is None:
            continue

        orig_len = len(ts.original_text)
        trans_len = len(ts.translated_text)

        # 1. Untranslated segment — text unchanged despite different languages.
        if source_lang != target_lang and ts.original_text == ts.translated_text:
            issues.append(
                QualityIssue(
                    segment_id=ts.id,
                    check_name="untranslated_segment",
                    message="Translated text is identical to original text.",
                )
            )
            continue  # Skip ratio checks — both would fire for untranslated text.

        # 2. Very short translation — might indicate truncation or refusal.
        if orig_len > 20 and trans_len > 0 and trans_len < orig_len * 0.20:
            issues.append(
                QualityIssue(
                    segment_id=ts.id,
                    check_name="short_translation",
                    message=(
                        f"Translation very short: {trans_len} chars "
                        f"vs {orig_len} original chars."
                    ),
                )
            )

        # 3. Hallucinated paragraph — translation much longer than original.
        if orig_len > 0 and trans_len > orig_len * 5:
            issues.append(
                QualityIssue(
                    segment_id=ts.id,
                    check_name="hallucinated_paragraph",
                    message=(
                        f"Translation suspiciously long: {trans_len} chars "
                        f"vs {orig_len} original chars."
                    ),
                )
            )

    return issues
