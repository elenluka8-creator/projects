from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

REQUIRED_BATCH_FIELDS = {"batch_id", "source_language", "target_language", "segments"}

FORBIDDEN_BATCH_KEYS = {
    "full_book",
    "book_text",
    "all_chapters",
    "chapter_list",
    "book_content",
}

MAX_SEGMENTS_PER_BATCH = 50
MAX_CONTEXT_SEGMENTS = 5


@dataclass(frozen=True)
class ProviderPayloadViolation:
    code: str
    message: str
    context: Dict[str, Any]


class ProviderPayloadPolicyError(Exception):
    def __init__(self, violation: ProviderPayloadViolation) -> None:
        super().__init__(violation.message)
        self.violation = violation


def _check_required_fields(payload: Dict[str, Any]) -> Optional[ProviderPayloadViolation]:
    missing = REQUIRED_BATCH_FIELDS - payload.keys()
    if missing:
        return ProviderPayloadViolation(
            code="MISSING_REQUIRED_FIELDS",
            message="Provider payload is missing required fields.",
            context={"missing_fields": sorted(missing)},
        )
    return None


def _check_forbidden_keys(payload: Dict[str, Any]) -> Optional[ProviderPayloadViolation]:
    found = FORBIDDEN_BATCH_KEYS & payload.keys()
    if found:
        return ProviderPayloadViolation(
            code="OVERSCOPED_PAYLOAD",
            message="Provider payload contains forbidden full-book or cross-chapter fields.",
            context={"forbidden_keys_found": sorted(found)},
        )
    return None


def _check_segment_count(payload: Dict[str, Any]) -> Optional[ProviderPayloadViolation]:
    segments = payload.get("segments")
    if not isinstance(segments, list):
        return ProviderPayloadViolation(
            code="INVALID_SEGMENTS",
            message="Provider payload 'segments' must be a list.",
            context={"segments_type": type(segments).__name__},
        )
    if len(segments) > MAX_SEGMENTS_PER_BATCH:
        return ProviderPayloadViolation(
            code="SEGMENTS_EXCEED_BATCH_LIMIT",
            message="Provider payload exceeds maximum segments per batch.",
            context={
                "segment_count": len(segments),
                "max_allowed": MAX_SEGMENTS_PER_BATCH,
            },
        )
    return None


def _check_context_segments(payload: Dict[str, Any]) -> Optional[ProviderPayloadViolation]:
    context_segments = payload.get("context_segments")
    if context_segments is None:
        return None
    if not isinstance(context_segments, list):
        return ProviderPayloadViolation(
            code="INVALID_CONTEXT_SEGMENTS",
            message="Provider payload 'context_segments' must be a list.",
            context={"context_segments_type": type(context_segments).__name__},
        )
    if len(context_segments) > MAX_CONTEXT_SEGMENTS:
        return ProviderPayloadViolation(
            code="CONTEXT_EXCEEDS_BOUND",
            message="Provider payload context_segments exceeds bounded consistency window.",
            context={
                "context_count": len(context_segments),
                "max_allowed": MAX_CONTEXT_SEGMENTS,
            },
        )
    return None


def validate_provider_payload(payload: Dict[str, Any]) -> None:
    """Validate a translation-provider batch payload before dispatch.

    Raises ProviderPayloadPolicyError on any policy violation.
    Violations are metadata-only — no raw text is included in error context.
    """
    checks = [
        _check_forbidden_keys,
        _check_required_fields,
        _check_segment_count,
        _check_context_segments,
    ]
    for check in checks:
        violation = check(payload)
        if violation is not None:
            raise ProviderPayloadPolicyError(violation)
