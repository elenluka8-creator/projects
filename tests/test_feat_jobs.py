"""Tests for FEAT-JOBS: job-receipt fields and download-url endpoint.

Covers:
- retention_deadline, retry_eligible, book_title, book_author in responses
- GET /jobs/{id}/download-url: 404 (job not found), 409 (not completed),
  404 (no output artifact), 410 (artifact deleted), 200 (success)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — registers all models with Base
from app.db.base import Base
from app.db.models.artifact import Artifact
from app.db.models.document import Document
from app.db.models.job import Job
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app
from app.api.routers.jobs import get_queue_broker
from app.queue.broker import InMemoryQueueBroker
from app.storage.client import FakeStorageClient, get_storage_client


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SECRET = "x" * 32


def _token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"user_id": user_id, "exp": int((now + timedelta(seconds=600)).timestamp())},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXTAUTH_SECRET", SECRET)
    monkeypatch.setenv("SIGNED_URL_MIN_EXPIRY_SECONDS", "60")
    monkeypatch.setenv("SIGNED_URL_MAX_EXPIRY_SECONDS", "900")
    monkeypatch.setenv("SIGNED_URL_BASE_URL", "https://fake.storage")


@pytest.fixture
def client(env):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSession()
    broker = InMemoryQueueBroker()
    fake_storage = FakeStorageClient()

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_queue_broker] = lambda: broker
    app.dependency_overrides[get_storage_client] = lambda: fake_storage

    yield TestClient(app), session, fake_storage

    session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def _make_user(session, balance: int = 1000) -> User:
    user = User(google_sub=f"sub-{uuid4()}", email=f"{uuid4()}@t.com")
    session.add(user)
    session.flush()
    session.add(UserCreditAccount(user_id=user.user_id, balance=balance))
    session.commit()
    return user


def _make_job(session, user: User, status: str = "queued", **kwargs) -> Job:
    job = Job(
        user_id=user.user_id,
        status=status,
        mode="translate",
        target_language="de",
        **kwargs,
    )
    session.add(job)
    session.commit()
    return job


def _make_document(session, job: Job, title: str = "Test Book", author: str = "Author X") -> Document:
    doc = Document(
        job_id=job.job_id,
        user_id=job.user_id,
        title=title,
        author=author,
        detected_language="en",
        detection_confidence=0.98,
        source_word_count=5000,
        chapter_count=10,
    )
    session.add(doc)
    session.commit()
    return doc


def _make_artifact(session, job: Job, storage_status: str = "active") -> Artifact:
    artifact = Artifact(
        user_id=job.user_id,
        job_id=job.job_id,
        artifact_type="output_epub",
        object_key=f"users/{job.user_id}/jobs/{job.job_id}/output_epub/{uuid4()}",
        storage_status=storage_status,
    )
    session.add(artifact)
    session.commit()
    return artifact


# ---------------------------------------------------------------------------
# Job-receipt field tests
# ---------------------------------------------------------------------------

def test_receipt_fields_present_in_get_job(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user)
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "retention_deadline" in data
    assert "retry_eligible" in data
    assert "book_title" in data
    assert "book_author" in data


def test_retry_eligible_true_for_failed_job_within_window(client):
    http, session, _ = client
    user = _make_user(session)
    future_deadline = datetime.now(timezone.utc) + timedelta(days=10)
    job = _make_job(session, user, status="failed", retention_deadline=future_deadline)
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["retry_eligible"] is True


def test_retry_eligible_false_for_completed_job(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user, status="completed")
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["retry_eligible"] is False


def test_retry_eligible_false_for_failed_job_past_deadline(client):
    http, session, _ = client
    user = _make_user(session)
    past_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    job = _make_job(session, user, status="failed", retention_deadline=past_deadline)
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["retry_eligible"] is False


def test_book_title_null_when_no_document(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user)
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["book_title"] is None
    assert resp.json()["book_author"] is None


def test_book_title_populated_when_document_exists(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user)
    _make_document(session, job, title="Crime and Punishment", author="Fyodor Dostoevsky")
    token = _token(str(user.user_id))

    resp = http.get(f"/jobs/{job.job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["book_title"] == "Crime and Punishment"
    assert resp.json()["book_author"] == "Fyodor Dostoevsky"


def test_list_jobs_includes_receipt_fields(client):
    http, session, _ = client
    user = _make_user(session)
    _make_job(session, user)
    token = _token(str(user.user_id))

    resp = http.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert "retry_eligible" in jobs[0]
    assert "book_title" in jobs[0]


# ---------------------------------------------------------------------------
# Download-url endpoint tests
# ---------------------------------------------------------------------------

def test_download_url_404_job_not_found(client):
    http, session, _ = client
    user = _make_user(session)
    token = _token(str(user.user_id))

    resp = http.get(
        f"/jobs/{uuid4()}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_download_url_409_when_job_not_completed(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user, status="queued")
    token = _token(str(user.user_id))

    resp = http.get(
        f"/jobs/{job.job_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert "not yet available" in resp.json()["detail"]["message"]


def test_download_url_404_when_no_output_artifact(client):
    http, session, _ = client
    user = _make_user(session)
    job = _make_job(session, user, status="completed")
    # output_artifact_id is None
    token = _token(str(user.user_id))

    resp = http.get(
        f"/jobs/{job.job_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert "No output artifact" in resp.json()["detail"]["message"]


def test_download_url_410_when_artifact_deleted(client):
    http, session, _ = client
    user = _make_user(session)
    artifact = _make_artifact(session, _make_job(session, user, status="completed"),
                               storage_status="deleted")
    # Retrieve the job we just created and set output_artifact_id
    job = session.query(Job).filter_by(user_id=user.user_id).first()
    job.output_artifact_id = artifact.artifact_id
    session.commit()
    token = _token(str(user.user_id))

    resp = http.get(
        f"/jobs/{job.job_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 410


def test_download_url_success(client):
    http, session, fake_storage = client
    user = _make_user(session)
    job = _make_job(session, user, status="completed")
    artifact = _make_artifact(session, job, storage_status="active")
    job.output_artifact_id = artifact.artifact_id
    session.commit()
    token = _token(str(user.user_id))

    resp = http.get(
        f"/jobs/{job.job_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job.job_id)
    assert data["artifact_id"] == str(artifact.artifact_id)
    assert "download_url" in data
    assert data["expires_in_seconds"] == 300
