from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import InMemoryOwnershipStore, get_ownership_store
from app.main import app
from app.security.audit_log import (
    AUDIT_BREAK_GLASS_ACCESS,
    AUDIT_POLICY_REJECTED,
    AUDIT_SIGNED_URL_ISSUED,
    emit_audit_event,
    emit_break_glass_audit_event,
)


def _token(secret: str, user_id: str, expires_seconds: int = 600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NEXTAUTH_SECRET", "x" * 32)
    monkeypatch.setenv("SIGNED_URL_MIN_EXPIRY_SECONDS", "60")
    monkeypatch.setenv("SIGNED_URL_MAX_EXPIRY_SECONDS", "900")
    return TestClient(app)


def test_emit_audit_event_logs_metadata_only(caplog: pytest.LogCaptureFixture) -> None:
    actor_id = uuid4()
    with caplog.at_level(logging.INFO, logger="app.security.audit_log"):
        emit_audit_event(
            action=AUDIT_SIGNED_URL_ISSUED,
            actor_id=actor_id,
            target="books/u1/ch1.epub",
            extra={"purpose": "upload", "expires_in_seconds": 300},
        )

    assert any("audit_event" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "audit_event" in r.message)
    assert record.__dict__.get("action") == AUDIT_SIGNED_URL_ISSUED
    assert record.__dict__.get("actor_id") == str(actor_id)
    assert record.__dict__.get("target") == "books/u1/ch1.epub"
    assert record.__dict__.get("audit") is True


def test_emit_break_glass_audit_event_requires_reason() -> None:
    with pytest.raises(ValueError, match="non-empty reason"):
        emit_break_glass_audit_event(
            actor_id=uuid4(),
            target="books/u1/restricted.epub",
            reason="   ",
        )


def test_emit_break_glass_audit_event_logs_at_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    actor_id = uuid4()
    with caplog.at_level(logging.WARNING, logger="app.security.audit_log"):
        emit_break_glass_audit_event(
            actor_id=actor_id,
            target="books/u1/restricted.epub",
            reason="Emergency support access for incident-42.",
        )

    assert any("break_glass_audit_event" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "break_glass_audit_event" in r.message)
    assert record.levelno == logging.WARNING
    assert record.__dict__.get("action") == AUDIT_BREAK_GLASS_ACCESS
    assert record.__dict__.get("break_glass") is True
    assert record.__dict__.get("reason") == "Emergency support access for incident-42."


def test_audit_record_contains_no_raw_book_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_text = "This is the entire raw book content that must never be logged."
    with caplog.at_level(logging.INFO, logger="app.security.audit_log"):
        emit_audit_event(
            action=AUDIT_POLICY_REJECTED,
            actor_id=uuid4(),
            target="books/u1/ch1.epub",
            reason="Policy violation.",
        )

    for record in caplog.records:
        assert raw_text not in str(record.__dict__)


def test_signed_url_issuance_emits_audit_event(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    owner_id = uuid4()
    object_key = "books/u1/audit-test.epub"

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(object_owners={object_key: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    with caplog.at_level(logging.INFO, logger="app.security.audit_log"):
        response = client.post(
            "/security/signed-urls",
            params={"object_key": object_key, "purpose": "upload", "expires_in_seconds": 300},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert any("audit_event" in r.message for r in caplog.records)
    audit_record = next(r for r in caplog.records if "audit_event" in r.message)
    assert audit_record.__dict__.get("action") == AUDIT_SIGNED_URL_ISSUED
    assert audit_record.__dict__.get("actor_id") == str(owner_id)
    app.dependency_overrides.clear()


def test_policy_rejection_emits_audit_event(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    owner_id = uuid4()
    object_key = "books/u1/reject-test.epub"

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(object_owners={object_key: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    with caplog.at_level(logging.INFO, logger="app.security.audit_log"):
        response = client.post(
            "/security/signed-urls",
            params={"object_key": object_key, "purpose": "download", "expires_in_seconds": 9999},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 400
    assert any("audit_event" in r.message for r in caplog.records)
    audit_record = next(r for r in caplog.records if "audit_event" in r.message)
    assert audit_record.__dict__.get("action") == AUDIT_POLICY_REJECTED
    app.dependency_overrides.clear()
