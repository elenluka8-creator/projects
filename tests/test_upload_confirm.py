"""Integration tests for confirm_upload domain service and POST /upload/confirm endpoint."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — register all models with Base
from app.db.base import Base
from app.db.models.artifact import Artifact
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app as fastapi_app
from app.storage.client import FakeStorageClient, get_storage_client
from app.upload.confirm import confirm_upload
from app.upload.validator import UploadValidationError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_epub() -> bytes:
    """Build a minimal valid EPUB3."""
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
        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Test Book</dc:title>"
            "</metadata>"
            "<manifest>"
            '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            "</manifest>"
            "<spine><itemref idref='ch1'/></spine>"
            "</package>",
        )
        zf.writestr("OEBPS/ch1.xhtml", "<html><body><p>Hello</p></body></html>")
    return buf.getvalue()


def _make_invalid_epub() -> bytes:
    return b"not a zip at all"


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
    session.flush()
    account = UserCreditAccount(
        account_id=uuid.uuid4(),
        user_id=user.user_id,
        balance=100,
    )
    session.add(account)
    session.flush()
    return user


def _make_artifact(session, user_id: uuid.UUID, artifact_type: str = "source_epub") -> Artifact:
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        user_id=user_id,
        job_id=uuid.uuid4(),
        artifact_type=artifact_type,
        object_key=f"users/{user_id}/jobs/{uuid.uuid4()}/source_epub/{uuid.uuid4()}",
        storage_status="active",
    )
    session.add(artifact)
    session.flush()
    return artifact


# ── Domain service tests ──────────────────────────────────────────────────────

def test_confirm_upload_success(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_artifact(db_session, user.user_id)
    client = FakeStorageClient()
    epub_bytes = _make_minimal_epub()
    client.put_object(artifact.object_key, epub_bytes)

    result = confirm_upload(
        session=db_session,
        client=client,
        artifact_id=artifact.artifact_id,
        user_id=user.user_id,
    )

    assert result.validated_at is not None
    assert result.content_sha256 is not None
    assert len(result.content_sha256) == 64
    assert result.mime_type == "application/epub+zip"
    assert result.size_bytes == len(epub_bytes)
    assert result.storage_status == "active"


def test_confirm_upload_idempotent(db_session) -> None:
    """Second call on already-validated artifact returns the same record."""
    user = _make_user(db_session)
    artifact = _make_artifact(db_session, user.user_id)
    client = FakeStorageClient()
    client.put_object(artifact.object_key, _make_minimal_epub())

    first = confirm_upload(db_session, client, artifact.artifact_id, user.user_id)
    second = confirm_upload(db_session, client, artifact.artifact_id, user.user_id)

    assert first.validated_at == second.validated_at
    assert first.content_sha256 == second.content_sha256


def test_confirm_upload_not_found_raises(db_session) -> None:
    user = _make_user(db_session)
    with pytest.raises(LookupError):
        confirm_upload(db_session, FakeStorageClient(), uuid.uuid4(), user.user_id)


def test_confirm_upload_wrong_owner_raises(db_session) -> None:
    user_a = _make_user(db_session)
    user_b = _make_user(db_session)
    artifact = _make_artifact(db_session, user_a.user_id)
    with pytest.raises(PermissionError):
        confirm_upload(db_session, FakeStorageClient(), artifact.artifact_id, user_b.user_id)


def test_confirm_upload_wrong_type_raises(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_artifact(db_session, user.user_id, artifact_type="output_epub")
    with pytest.raises(ValueError, match="source_epub"):
        confirm_upload(db_session, FakeStorageClient(), artifact.artifact_id, user.user_id)


def test_confirm_upload_invalid_epub_marks_deleted(db_session) -> None:
    user = _make_user(db_session)
    artifact = _make_artifact(db_session, user.user_id)
    client = FakeStorageClient()
    client.put_object(artifact.object_key, _make_invalid_epub())

    with pytest.raises(UploadValidationError) as exc_info:
        confirm_upload(db_session, client, artifact.artifact_id, user.user_id)

    assert exc_info.value.code == "invalid_epub"
    db_session.refresh(artifact)
    assert artifact.storage_status == "deleted"
    assert artifact.deleted_at is not None


# ── API endpoint tests ────────────────────────────────────────────────────────

@pytest.fixture()
def api_client(db_session):
    """TestClient with DB and storage overrides."""
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


def _auth_headers(user_id: uuid.UUID, monkeypatch) -> dict:
    """Override get_current_user to return a fixed user_id."""
    from app.api.dependencies import get_current_user

    fastapi_app.dependency_overrides[get_current_user] = lambda: user_id
    return {}


def test_endpoint_confirm_valid_epub(api_client, monkeypatch) -> None:
    client, session, storage = api_client
    user = _make_user(session)
    artifact = _make_artifact(session, user.user_id)
    storage.put_object(artifact.object_key, _make_minimal_epub())
    _auth_headers(user.user_id, monkeypatch)

    resp = client.post(f"/upload/confirm/{artifact.artifact_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact_id"] == str(artifact.artifact_id)
    assert len(body["content_sha256"]) == 64
    assert body["mime_type"] == "application/epub+zip"
    assert body["size_bytes"] > 0
    assert body["validated_at"] != ""


def test_endpoint_confirm_not_found(api_client, monkeypatch) -> None:
    client, session, _ = api_client
    user = _make_user(session)
    _auth_headers(user.user_id, monkeypatch)

    resp = client.post(f"/upload/confirm/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_endpoint_confirm_wrong_owner(api_client, monkeypatch) -> None:
    client, session, storage = api_client
    user_a = _make_user(session)
    user_b = _make_user(session)
    artifact = _make_artifact(session, user_a.user_id)
    storage.put_object(artifact.object_key, _make_minimal_epub())
    _auth_headers(user_b.user_id, monkeypatch)

    resp = client.post(f"/upload/confirm/{artifact.artifact_id}")
    assert resp.status_code == 403


def test_endpoint_confirm_invalid_epub_returns_422(api_client, monkeypatch) -> None:
    client, session, storage = api_client
    user = _make_user(session)
    artifact = _make_artifact(session, user.user_id)
    storage.put_object(artifact.object_key, _make_invalid_epub())
    _auth_headers(user.user_id, monkeypatch)

    resp = client.post(f"/upload/confirm/{artifact.artifact_id}")
    assert resp.status_code == 422
    assert resp.json()["detail"]["context"]["code"] == "invalid_epub"
