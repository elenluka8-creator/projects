from __future__ import annotations

from app.api.errors import build_safe_error_detail
from app.security.payload_guard import REDACTION_MARKER


def test_build_safe_error_detail_redacts_raw_text_context() -> None:
    detail = build_safe_error_detail(
        message="Policy violation.",
        context={
            "job_id": "job-1",
            "source_text": "Sensitive source content that should not leak",
            "nested": {"translated_text": "Sensitive translated content"},
        },
    )

    assert detail["message"] == "Policy violation."
    assert detail["context"]["job_id"] == "job-1"
    assert detail["context"]["source_text"] == REDACTION_MARKER
    assert detail["context"]["nested"]["translated_text"] == REDACTION_MARKER
