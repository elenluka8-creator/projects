"""Tests for the notifications module (email_client and notification_service)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.notifications.email_client import send_email
from app.notifications.notification_service import send_job_completion_notification


# ---------------------------------------------------------------------------
# send_email tests
# ---------------------------------------------------------------------------


def test_send_email_missing_api_key_returns_false(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    result = send_email(to="user@example.com", subject="Hello", text_body="Body")
    assert result is False


def test_send_email_missing_api_key_makes_no_http_call(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with patch("app.notifications.email_client.httpx.post") as mock_post:
        send_email(to="user@example.com", subject="Hello", text_body="Body")
        mock_post.assert_not_called()


def test_send_email_success_returns_true(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    with patch("app.notifications.email_client.httpx.post", return_value=mock_response):
        result = send_email(to="user@example.com", subject="Hello", text_body="Body")
    assert result is True


def test_send_email_http_error_returns_false(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=MagicMock(), response=MagicMock()
    )
    with patch("app.notifications.email_client.httpx.post", return_value=mock_response):
        result = send_email(to="user@example.com", subject="Hello", text_body="Body")
    assert result is False


def test_send_email_http_error_does_not_raise(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    with patch("app.notifications.email_client.httpx.post", return_value=mock_response):
        # Must not raise
        send_email(to="user@example.com", subject="Hello", text_body="Body")


def test_send_email_network_error_returns_false(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    with patch(
        "app.notifications.email_client.httpx.post",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        result = send_email(to="user@example.com", subject="Hello", text_body="Body")
    assert result is False


def test_send_email_network_error_does_not_raise(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    with patch(
        "app.notifications.email_client.httpx.post",
        side_effect=Exception("unexpected"),
    ):
        # Must not raise
        send_email(to="user@example.com", subject="Hello", text_body="Body")


# ---------------------------------------------------------------------------
# send_job_completion_notification tests
# ---------------------------------------------------------------------------


def _make_job_id() -> uuid.UUID:
    return uuid.uuid4()


def test_notification_uses_stored_locale_when_supported():
    job_id = _make_job_id()
    user_id = _make_job_id()
    calls = []

    def fake_send(to, subject, text_body):
        calls.append({"to": to, "subject": subject, "body": text_body})
        return True

    with patch("app.notifications.notification_service.send_email", side_effect=fake_send):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="Don Quixote",
            ui_locale="es",
            base_url="https://app.unfolda.app",
        )

    assert len(calls) == 1
    # Spanish template subject
    assert "libro" in calls[0]["subject"].lower() or "listo" in calls[0]["subject"].lower()


def test_notification_falls_back_to_english_for_unsupported_locale():
    job_id = _make_job_id()
    user_id = _make_job_id()
    calls = []

    def fake_send(to, subject, text_body):
        calls.append({"to": to, "subject": subject, "body": text_body})
        return True

    with patch("app.notifications.notification_service.send_email", side_effect=fake_send):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="xx",  # unsupported
            base_url="https://app.unfolda.app",
        )

    assert len(calls) == 1
    # English template subject
    assert "ready" in calls[0]["subject"].lower()


def test_notification_falls_back_to_english_when_locale_is_none():
    job_id = _make_job_id()
    user_id = _make_job_id()
    calls = []

    def fake_send(to, subject, text_body):
        calls.append({"to": to, "subject": subject, "body": text_body})
        return True

    with patch("app.notifications.notification_service.send_email", side_effect=fake_send):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale=None,
            base_url="https://app.unfolda.app",
        )

    assert len(calls) == 1
    assert "ready" in calls[0]["subject"].lower()


def test_notification_is_nonfatal_when_send_email_fails():
    job_id = _make_job_id()
    user_id = _make_job_id()

    with patch(
        "app.notifications.notification_service.send_email", return_value=False
    ):
        # Must not raise
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="en",
            base_url="https://app.unfolda.app",
        )


def test_notification_is_nonfatal_when_send_email_raises():
    job_id = _make_job_id()
    user_id = _make_job_id()

    with patch(
        "app.notifications.notification_service.send_email",
        side_effect=RuntimeError("boom"),
    ):
        # Must not raise
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="en",
            base_url="https://app.unfolda.app",
        )


def test_notification_dispatched_event_is_logged():
    job_id = _make_job_id()
    user_id = _make_job_id()
    logged_calls = []

    def fake_log_structured(logger, level, message, payload=None, **kwargs):
        logged_calls.append({"message": message, "payload": payload or {}})

    with (
        patch("app.notifications.notification_service.send_email", return_value=True),
        patch(
            "app.notifications.notification_service.log_structured",
            side_effect=fake_log_structured,
        ),
    ):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="en",
            base_url="https://app.unfolda.app",
        )

    dispatched_events = [c for c in logged_calls if c["message"] == "notification_dispatched"]
    assert len(dispatched_events) == 1
    payload = dispatched_events[0]["payload"]
    assert payload["job_id"] == str(job_id)
    assert payload["user_id"] == str(user_id)
    assert payload["ui_locale"] == "en"
    assert payload["locale_source"] == "stored"
    assert payload["success"] is True
    assert payload["failure_reason"] is None
    assert isinstance(payload["duration_ms"], int)
    assert "timestamp" in payload


def test_notification_dispatched_event_emitted_on_exception():
    """Event must be emitted even when send_email raises."""
    job_id = _make_job_id()
    user_id = _make_job_id()
    logged_calls = []

    def fake_log_structured(logger, level, message, payload=None, **kwargs):
        logged_calls.append({"message": message, "payload": payload or {}})

    with (
        patch(
            "app.notifications.notification_service.send_email",
            side_effect=RuntimeError("unexpected"),
        ),
        patch(
            "app.notifications.notification_service.log_structured",
            side_effect=fake_log_structured,
        ),
    ):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="en",
            base_url="https://app.unfolda.app",
        )

    dispatched_events = [c for c in logged_calls if c["message"] == "notification_dispatched"]
    assert len(dispatched_events) == 1
    payload = dispatched_events[0]["payload"]
    assert payload["success"] is False
    assert payload["failure_reason"] is not None
    assert isinstance(payload["duration_ms"], int)


def test_notification_failure_reason_api_key_missing(monkeypatch):
    """failure_reason='api_key_missing' when RESEND_API_KEY is absent."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    job_id = _make_job_id()
    user_id = _make_job_id()
    logged_calls = []

    def fake_log_structured(logger, level, message, payload=None, **kwargs):
        logged_calls.append({"message": message, "payload": payload or {}})

    with patch(
        "app.notifications.notification_service.log_structured",
        side_effect=fake_log_structured,
    ):
        send_job_completion_notification(
            job_id=job_id,
            user_id=user_id,
            user_email="user@example.com",
            display_name="Alice",
            book_title="My Book",
            ui_locale="en",
            base_url="https://app.unfolda.app",
        )

    dispatched_events = [c for c in logged_calls if c["message"] == "notification_dispatched"]
    assert len(dispatched_events) == 1
    payload = dispatched_events[0]["payload"]
    assert payload["success"] is False
    assert payload["failure_reason"] == "api_key_missing"
