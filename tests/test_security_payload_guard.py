from __future__ import annotations

from uuid import uuid4

from app.analytics.events import emit_event
from app.security.payload_guard import (
    REDACTION_MARKER,
    contains_forbidden_content,
    sanitize_for_logging_payload,
)


def test_sanitize_for_logging_payload_redacts_forbidden_fields() -> None:
    payload = {
        "event_name": "job_failed",
        "source_text": "This is sensitive source paragraph that should never be emitted.",
        "nested": {"translated_text": "Sensitive translation should be removed."},
        "items": [
            {"paragraph_text": "Sensitive paragraph."},
            "safe-value",
        ],
    }

    sanitized = sanitize_for_logging_payload(payload)

    assert sanitized["event_name"] == "job_failed"
    assert sanitized["source_text"] == REDACTION_MARKER
    assert sanitized["nested"]["translated_text"] == REDACTION_MARKER
    assert sanitized["items"][0]["paragraph_text"] == REDACTION_MARKER


def test_contains_forbidden_content_detects_forbidden_keys() -> None:
    assert contains_forbidden_content({"metadata": "ok", "source_text": "secret"}) is True
    assert contains_forbidden_content({"event_name": "user_signed_in", "user_id": "u-1"}) is False


def test_emit_event_logs_analytics_event_for_safe_payload(
    monkeypatch,
) -> None:
    captured: list[tuple[str, dict]] = []

    def fake_log_structured(logger, level, message, payload=None, exc_info=False):
        captured.append((message, payload or {}))

    monkeypatch.setattr("app.analytics.events.log_structured", fake_log_structured)

    emit_event("user_signed_in", uuid4())

    assert captured
    assert captured[0][0] == "analytics_event"
    assert captured[0][1]["event_name"] == "user_signed_in"


def test_emit_event_rejects_payload_when_guard_flags_content(
    monkeypatch,
) -> None:
    captured: list[tuple[str, dict]] = []

    def fake_log_structured(logger, level, message, payload=None, exc_info=False):
        captured.append((message, payload or {}))

    monkeypatch.setattr("app.analytics.events.log_structured", fake_log_structured)
    monkeypatch.setattr("app.analytics.events.contains_forbidden_content", lambda payload: True)

    emit_event("user_registered", uuid4())

    assert captured
    assert captured[0][0] == "Analytics payload rejected by payload guard."
