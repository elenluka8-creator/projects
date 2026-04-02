"""Tests for PRECHECK domain service and API endpoints.

Uses the existing epub_parser indirectly via the service, and mocks
the storage client to inject EPUB bytes.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — register all models
from app.db.base import Base
from app.db.models.artifact import Artifact
from app.db.models.precheck import PreCheckResult
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app as fastapi_app
from app.precheck.service import run_precheck
from app.storage.client import FakeStorageClient, get_storage_client
from app.api.dependencies import get_current_user


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


def _make_user(session) -> User:
    user = User(
        user_id=uuid.uuid4(),
        google_sub=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        is_admin=False,
    )
    session.add(user)
    account = UserCreditAccount(
        account_id=uuid.uuid4(),
        user_id=user.user_id,
        balance=100,
    )
    session.add(account)
    session.flush()
    return user


def _make_validated_artifact(session, user_id: uuid.UUID) -> Artifact:
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        user_id=user_id,
        job_id=uuid.uuid4(),
        artifact_type="source_epub",
        object_key=f"users/{user_id}/source/{uuid.uuid4()}",
        storage_status="active",
        content_sha256="a" * 64,
        mime_type="application/epub+zip",
        validated_at=datetime.now(timezone.utc),
        size_bytes=1024,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _make_minimal_epub(with_image: bool = False) -> bytes:
    """Build a minimal valid EPUB3 with extractable text."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0"'
            ' xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf"'
            ' media-type="application/oebps-package+xml"/>'
            "</rootfiles>"
            "</container>",
        )
        items = '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        if with_image:
            items += '<item id="img1" href="img1.png" media-type="image/png"/>'
        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Test Book</dc:title>"
            "<dc:creator>Author</dc:creator>"
            "<dc:language>en</dc:language>"
            "</metadata>"
            f"<manifest>{items}</manifest>"
            "<spine><itemref idref='ch1'/></spine>"
            "</package>",
        )
        zf.writestr(
            "OEBPS/ch1.xhtml",
            "<html><body>"
            "<h1>Chapter One</h1>"
            "<p>The quick brown fox jumps over the lazy dog. "
            "This is a test book for language detection purposes.</p>"
            "</body></html>",
        )
        if with_image:
            zf.writestr("OEBPS/img1.png", b"\x89PNG\r\n\x1a\n")
    return buf.getvalue()


def _make_bad_epub() -> bytes:
    return b"not a valid epub"


# ── Domain service tests ──────────────────────────────────────────────────────

def test_run_precheck_success(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    storage = FakeStorageClient()
    storage.put_object(artifact.object_key, _make_minimal_epub())

    result = run_precheck(
        session=db_session,
        client=storage,
        artifact_id=artifact.artifact_id,
        user_id=user.user_id,
    )

    assert result.status == "completed"
    assert result.word_count is not None and result.word_count > 0
    assert result.chapter_count == 1
    assert result.detected_language is not None
    assert result.language_confidence is not None
    assert result.completed_at is not None
    assert result.has_images is False


def test_run_precheck_detects_images(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    storage = FakeStorageClient()
    storage.put_object(artifact.object_key, _make_minimal_epub(with_image=True))

    result = run_precheck(
        session=db_session,
        client=storage,
        artifact_id=artifact.artifact_id,
        user_id=user.user_id,
    )

    assert result.status == "completed"
    assert result.has_images is True


def test_run_precheck_idempotent(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    storage = FakeStorageClient()
    storage.put_object(artifact.object_key, _make_minimal_epub())

    first = run_precheck(db_session, storage, artifact.artifact_id, user.user_id)
    db_session.commit()
    second = run_precheck(db_session, storage, artifact.artifact_id, user.user_id)

    assert first.precheck_id == second.precheck_id
    assert first.word_count == second.word_count


def test_run_precheck_not_found_raises(db_session) -> None:
    user = _make_user(db_session)
    with pytest.raises(LookupError):
        run_precheck(db_session, FakeStorageClient(), uuid.uuid4(), user.user_id)


def test_run_precheck_wrong_owner_raises(db_session) -> None:
    user_a = _make_user(db_session)
    user_b = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user_a.user_id)
    with pytest.raises(PermissionError):
        run_precheck(db_session, FakeStorageClient(), artifact.artifact_id, user_b.user_id)


def test_run_precheck_unvalidated_artifact_raises(db_session) -> None:
    user = _make_user(db_session)
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        user_id=user.user_id,
        job_id=uuid.uuid4(),
        artifact_type="source_epub",
        object_key=f"users/{user.user_id}/unvalidated/{uuid.uuid4()}",
        storage_status="active",
        # validated_at is None
    )
    db_session.add(artifact)
    db_session.flush()
    with pytest.raises(ValueError, match="validated"):
        run_precheck(db_session, FakeStorageClient(), artifact.artifact_id, user.user_id)


def test_run_precheck_wrong_artifact_type_raises(db_session) -> None:
    user = _make_user(db_session)
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        user_id=user.user_id,
        job_id=uuid.uuid4(),
        artifact_type="output_epub",
        object_key=f"users/{user.user_id}/output/{uuid.uuid4()}",
        storage_status="active",
        validated_at=datetime.now(timezone.utc),
    )
    db_session.add(artifact)
    db_session.flush()
    with pytest.raises(ValueError, match="source_epub"):
        run_precheck(db_session, FakeStorageClient(), artifact.artifact_id, user.user_id)


def test_run_precheck_storage_failure_returns_failed_record(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    # Empty storage — get_object_bytes will raise KeyError
    storage = FakeStorageClient()

    result = run_precheck(
        session=db_session,
        client=storage,
        artifact_id=artifact.artifact_id,
        user_id=user.user_id,
    )

    assert result.status == "failed"
    assert result.error_code == "storage_unavailable"
    assert result.completed_at is not None


def test_run_precheck_parse_failure_returns_failed_record(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    storage = FakeStorageClient()
    storage.put_object(artifact.object_key, _make_bad_epub())

    result = run_precheck(
        session=db_session,
        client=storage,
        artifact_id=artifact.artifact_id,
        user_id=user.user_id,
    )

    assert result.status == "failed"
    assert result.error_code in ("epub_parse_failed", "drm_detected")


def test_run_precheck_language_detection_failure_falls_back(db_session) -> None:
    """Language detection failure falls back to 'unknown' — not a failing state."""
    user = _make_user(db_session)
    artifact = _make_validated_artifact(db_session, user.user_id)
    storage = FakeStorageClient()
    storage.put_object(artifact.object_key, _make_minimal_epub())

    with patch(
        "app.pipeline.ingestion.language_detector.LanguageDetector",
        side_effect=RuntimeError("detection unavailable"),
    ):
        result = run_precheck(
            session=db_session,
            client=storage,
            artifact_id=artifact.artifact_id,
            user_id=user.user_id,
        )

    assert result.status == "completed"
    assert result.detected_language == "unknown"
    assert result.language_confidence == 0.0


# ── API endpoint tests ────────────────────────────────────────────────────────

@pytest.fixture()
def api_client(db_session):
    fake_storage = FakeStorageClient()

    def override_db():
        yield db_session

    def override_storage():
        return fake_storage

    fastapi_app.dependency_overrides[get_db_session] = override_db
    fastapi_app.dependency_overrides[get_storage_client] = override_storage

    client = TestClient(fastapi_app, raise_server_exceptions=False)
    yield client, db_session, fake_storage
    fastapi_app.dependency_overrides.clear()


def test_endpoint_post_precheck_success(api_client) -> None:
    client, session, storage = api_client
    user = _make_user(session)
    artifact = _make_validated_artifact(session, user.user_id)
    storage.put_object(artifact.object_key, _make_minimal_epub())
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post(f"/precheck/{artifact.artifact_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["artifact_id"] == str(artifact.artifact_id)
    assert body["word_count"] is not None and body["word_count"] > 0
    assert body["chapter_count"] == 1
    assert body["detected_language"] is not None
    assert body["has_images"] is False


def test_endpoint_post_precheck_not_found(api_client) -> None:
    client, session, _ = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post(f"/precheck/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_endpoint_post_precheck_wrong_owner(api_client) -> None:
    client, session, storage = api_client
    user_a = _make_user(session)
    user_b = _make_user(session)
    artifact = _make_validated_artifact(session, user_a.user_id)
    storage.put_object(artifact.object_key, _make_minimal_epub())
    fastapi_app.dependency_overrides[get_current_user] = lambda: user_b.user_id

    resp = client.post(f"/precheck/{artifact.artifact_id}")
    assert resp.status_code == 403


def test_endpoint_get_precheck_success(api_client) -> None:
    client, session, storage = api_client
    user = _make_user(session)
    artifact = _make_validated_artifact(session, user.user_id)
    storage.put_object(artifact.object_key, _make_minimal_epub())
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    # Trigger first
    post_resp = client.post(f"/precheck/{artifact.artifact_id}")
    assert post_resp.status_code == 200

    # Then retrieve
    get_resp = client.get(f"/precheck/{artifact.artifact_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["status"] == "completed"
    assert body["precheck_id"] == post_resp.json()["precheck_id"]


def test_endpoint_get_precheck_not_found(api_client) -> None:
    client, session, _ = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.get(f"/precheck/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_endpoint_post_precheck_unvalidated_artifact_returns_400(api_client) -> None:
    client, session, _ = api_client
    user = _make_user(session)
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        user_id=user.user_id,
        job_id=uuid.uuid4(),
        artifact_type="source_epub",
        object_key=f"users/{user.user_id}/raw/{uuid.uuid4()}",
        storage_status="active",
    )
    session.add(artifact)
    session.flush()
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post(f"/precheck/{artifact.artifact_id}")
    assert resp.status_code == 400
