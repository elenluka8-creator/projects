from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.db.models  # noqa: F401 — ensures all models are registered with Base
from app.db.models.artifact import ARTIFACT_TYPES, Artifact
from app.security.signed_url_policy import SignedUrlPolicyConfig
from app.storage.client import FakeStorageClient
from app.storage.service import (
    build_object_key,
    issue_download_url,
    mark_artifact_deleted,
    register_artifact,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def fake_client() -> FakeStorageClient:
    return FakeStorageClient()


@pytest.fixture
def policy() -> SignedUrlPolicyConfig:
    return SignedUrlPolicyConfig(
        min_expiry_seconds=60,
        max_expiry_seconds=900,
        base_url="https://storage.example.com",
    )


def test_build_object_key_follows_namespace() -> None:
    user_id = uuid4()
    job_id = uuid4()
    artifact_id = uuid4()

    key = build_object_key(
        user_id=user_id,
        job_id=job_id,
        artifact_type="source_epub",
        artifact_id=artifact_id,
    )

    assert key == f"users/{user_id}/jobs/{job_id}/source_epub/{artifact_id}"


def test_register_artifact_creates_db_record_and_returns_url(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    user_id = uuid4()
    job_id = uuid4()

    artifact, upload_url = register_artifact(
        session=db_session,
        client=fake_client,
        user_id=user_id,
        job_id=job_id,
        artifact_type="source_epub",
        size_bytes=102400,
        expires_in_seconds=300,
        policy_config=policy,
    )

    assert artifact.artifact_id is not None
    assert artifact.user_id == user_id
    assert artifact.job_id == job_id
    assert artifact.artifact_type == "source_epub"
    assert artifact.storage_status == "active"
    assert "source_epub" in artifact.object_key
    assert str(user_id) in artifact.object_key
    assert str(job_id) in artifact.object_key
    assert "upload" in upload_url


def test_register_artifact_rejects_invalid_artifact_type(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    with pytest.raises(ValueError, match="Invalid artifact_type"):
        register_artifact(
            session=db_session,
            client=fake_client,
            user_id=uuid4(),
            job_id=uuid4(),
            artifact_type="unknown_type",
            size_bytes=None,
            expires_in_seconds=300,
            policy_config=policy,
        )


def test_register_artifact_enforces_min_expiry(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    with pytest.raises(ValueError, match="below minimum"):
        register_artifact(
            session=db_session,
            client=fake_client,
            user_id=uuid4(),
            job_id=uuid4(),
            artifact_type="output_epub",
            size_bytes=None,
            expires_in_seconds=10,
            policy_config=policy,
        )


def test_register_artifact_enforces_max_expiry(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    with pytest.raises(ValueError, match="exceeds maximum"):
        register_artifact(
            session=db_session,
            client=fake_client,
            user_id=uuid4(),
            job_id=uuid4(),
            artifact_type="output_epub",
            size_bytes=None,
            expires_in_seconds=9999,
            policy_config=policy,
        )


def test_issue_download_url_returns_url_for_owner(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    user_id = uuid4()
    job_id = uuid4()

    artifact, _ = register_artifact(
        session=db_session,
        client=fake_client,
        user_id=user_id,
        job_id=job_id,
        artifact_type="output_epub",
        size_bytes=None,
        expires_in_seconds=300,
        policy_config=policy,
    )

    download_url = issue_download_url(
        session=db_session,
        client=fake_client,
        artifact_id=artifact.artifact_id,
        user_id=user_id,
        expires_in_seconds=300,
        policy_config=policy,
    )

    assert "download" in download_url
    assert artifact.object_key.replace("/", "%") or artifact.object_key in download_url


def test_issue_download_url_denies_cross_user_access(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()

    artifact, _ = register_artifact(
        session=db_session,
        client=fake_client,
        user_id=owner_id,
        job_id=uuid4(),
        artifact_type="source_epub",
        size_bytes=None,
        expires_in_seconds=300,
        policy_config=policy,
    )

    with pytest.raises(PermissionError):
        issue_download_url(
            session=db_session,
            client=fake_client,
            artifact_id=artifact.artifact_id,
            user_id=other_user_id,
            expires_in_seconds=300,
            policy_config=policy,
        )


def test_issue_download_url_raises_for_unknown_artifact(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    with pytest.raises(LookupError):
        issue_download_url(
            session=db_session,
            client=fake_client,
            artifact_id=uuid4(),
            user_id=uuid4(),
            expires_in_seconds=300,
            policy_config=policy,
        )


def test_mark_artifact_deleted_sets_status(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    user_id = uuid4()

    artifact, _ = register_artifact(
        session=db_session,
        client=fake_client,
        user_id=user_id,
        job_id=uuid4(),
        artifact_type="translation_batch_artifact",
        size_bytes=None,
        expires_in_seconds=300,
        policy_config=policy,
    )

    mark_artifact_deleted(session=db_session, artifact_id=artifact.artifact_id)
    db_session.flush()

    refreshed = db_session.get(Artifact, artifact.artifact_id)
    assert refreshed is not None
    assert refreshed.storage_status == "deleted"
    assert refreshed.deleted_at is not None


def test_issue_download_url_raises_for_deleted_artifact(
    db_session: Session,
    fake_client: FakeStorageClient,
    policy: SignedUrlPolicyConfig,
) -> None:
    user_id = uuid4()

    artifact, _ = register_artifact(
        session=db_session,
        client=fake_client,
        user_id=user_id,
        job_id=uuid4(),
        artifact_type="consistency_memory_snapshot",
        size_bytes=None,
        expires_in_seconds=300,
        policy_config=policy,
    )
    mark_artifact_deleted(session=db_session, artifact_id=artifact.artifact_id)
    db_session.flush()

    with pytest.raises(LookupError):
        issue_download_url(
            session=db_session,
            client=fake_client,
            artifact_id=artifact.artifact_id,
            user_id=user_id,
            expires_in_seconds=300,
            policy_config=policy,
        )
