from __future__ import annotations

import pytest

from app.security.provider_payload_validator import (
    MAX_CONTEXT_SEGMENTS,
    MAX_SEGMENTS_PER_BATCH,
    ProviderPayloadPolicyError,
    validate_provider_payload,
)


def _minimal_valid_payload(**overrides) -> dict:
    base = {
        "batch_id": "batch-001",
        "source_language": "en",
        "target_language": "de",
        "segments": ["Hello world.", "How are you?"],
    }
    base.update(overrides)
    return base


def test_accepts_minimal_valid_payload() -> None:
    validate_provider_payload(_minimal_valid_payload())


def test_accepts_payload_with_bounded_context_segments() -> None:
    payload = _minimal_valid_payload(
        context_segments=["Previous sentence one.", "Previous sentence two."]
    )
    validate_provider_payload(payload)


def test_rejects_payload_missing_required_fields() -> None:
    payload = {"batch_id": "b1", "source_language": "en"}
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "MISSING_REQUIRED_FIELDS"
    assert "target_language" in exc_info.value.violation.context["missing_fields"]
    assert "segments" in exc_info.value.violation.context["missing_fields"]


def test_rejects_payload_with_full_book_field() -> None:
    payload = _minimal_valid_payload(full_book="entire book content here")
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "OVERSCOPED_PAYLOAD"
    assert "full_book" in exc_info.value.violation.context["forbidden_keys_found"]


def test_rejects_payload_with_all_chapters_field() -> None:
    payload = _minimal_valid_payload(all_chapters=["ch1", "ch2", "ch3"])
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "OVERSCOPED_PAYLOAD"


def test_rejects_payload_exceeding_max_segments() -> None:
    payload = _minimal_valid_payload(
        segments=[f"Sentence {i}." for i in range(MAX_SEGMENTS_PER_BATCH + 1)]
    )
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "SEGMENTS_EXCEED_BATCH_LIMIT"
    assert exc_info.value.violation.context["segment_count"] == MAX_SEGMENTS_PER_BATCH + 1
    assert exc_info.value.violation.context["max_allowed"] == MAX_SEGMENTS_PER_BATCH


def test_rejects_payload_exceeding_max_context_segments() -> None:
    payload = _minimal_valid_payload(
        context_segments=[f"Context {i}." for i in range(MAX_CONTEXT_SEGMENTS + 1)]
    )
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "CONTEXT_EXCEEDS_BOUND"
    assert exc_info.value.violation.context["context_count"] == MAX_CONTEXT_SEGMENTS + 1


def test_policy_error_detail_contains_no_raw_text() -> None:
    payload = _minimal_valid_payload(full_book="This is the entire raw book text...")
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    violation = exc_info.value.violation
    context_str = str(violation.context)
    assert "raw book text" not in context_str
    assert "entire" not in context_str


def test_rejects_segments_that_is_not_a_list() -> None:
    payload = _minimal_valid_payload(segments="not a list")
    with pytest.raises(ProviderPayloadPolicyError) as exc_info:
        validate_provider_payload(payload)
    assert exc_info.value.violation.code == "INVALID_SEGMENTS"
