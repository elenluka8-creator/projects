"""Integration tests for CleanupWorker."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.artifact import Artifact
from app.db.models.job import Job, JobRun
from app.db.models.job_event import JobEvent
from app.db.models.user import User, UserCreditAccount
from app.retention.cleanup import CleanupWorker
from app.storage.client import FakeStorageClient


@pytest.fixture
def session():
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
    u = User(google_sub=f"sub-{uuid.uuid4()}", email="c@example.com")
    session.add(u)
    session.flush()
    session.add(UserCreditAccount(user_id=u.user_id, balance=0))
    session.flush()
    return u


def _make_job(session, user: User, status: str = "completed", past_deadline: bool = True) -> Job:
    deadline = datetime.now(timezone.utc) - timedelta(days=1) if past_deadline else \
               datetime.now(timezone.utc) + timedelta(days=30)
    job = Job(
        user_id=user.user_id,
        status=status,
        mode="translate",
        target_language="de",
        retention_deadline=deadline,
    )
    session.add(job)
    session.flush()
    return job


def _make_artifact(session, user: User, job: Job, key: str = None) -> Artifact:
    key = key or f"users/{user.user_id}/jobs/{job.job_id}/source_epub/{uuid.uuid4()}"
    art = Artifact(
        user_id=user.user_id,
        job_id=job.job_id,
        artifact_type="source_epub",
        object_key=key,
        storage_status="active",
    )
    session.add(art)
    session.flush()
    return art


def _make_fake_storage_with_object(key: str) -> FakeStorageClient:
    """Return a FakeStorageClient pre-seeded with a single object."""
    storage = FakeStorageClient()
    # FakeStorageClient uses an in-memory dict; seed via upload URL mechanism
    # For tests we can seed directly through internal dict if available,
    # otherwise just rely on delete_object being a no-op (FakeStorageClient doesn't raise).
    return storage


def test_run_once_returns_zero_when_no_eligible_jobs(session):
    worker = CleanupWorker()
    storage = FakeStorageClient()
    count = worker.run_once(session, storage)
    assert count == 0


def test_run_once_expires_job_past_deadline(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 1
    session.refresh(job)
    assert job.status == "expired"


def test_run_once_deletes_active_artifacts(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)
    art = _make_artifact(session, user, job)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    worker.run_once(session, storage)

    session.refresh(art)
    assert art.storage_status == "deleted"
    assert art.deleted_at is not None


def test_run_once_skips_future_deadline(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=False)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 0
    session.refresh(job)
    assert job.status == "completed"


def test_run_once_skips_active_job(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)

    # Add an active job_run
    run = JobRun(
        job_id=job.job_id,
        user_id=user.user_id,
        status="processing",
        pipeline_version="0.1",
    )
    session.add(run)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 0
    session.refresh(job)
    assert job.status == "completed"


def test_run_once_emits_timeline_events(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    worker.run_once(session, storage)

    events = session.query(JobEvent).filter_by(job_id=job.job_id).all()
    event_types = {e.event_type for e in events}

    assert "cleanup_started" in event_types
    assert "cleanup_completed" in event_types
    assert "job_expired" in event_types


def test_run_once_idempotent_on_already_expired(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    # Job already expired — not in terminal_statuses query
    job = _make_job(session, user, status="expired", past_deadline=True)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 0


def test_run_once_handles_multiple_artifacts(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)
    art1 = _make_artifact(session, user, job, key=f"users/{user.user_id}/jobs/{job.job_id}/file1")
    art2 = _make_artifact(session, user, job, key=f"users/{user.user_id}/jobs/{job.job_id}/file2")
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 1
    session.refresh(art1)
    session.refresh(art2)
    assert art1.storage_status == "deleted"
    assert art2.storage_status == "deleted"


def test_run_once_skips_already_deleted_artifacts(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="completed", past_deadline=True)

    # Artifact already deleted
    art = Artifact(
        user_id=user.user_id,
        job_id=job.job_id,
        artifact_type="source_epub",
        object_key=f"users/{user.user_id}/jobs/{job.job_id}/already_deleted",
        storage_status="deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    session.add(art)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    # Job still expires even if artifact was already deleted
    assert count == 1
    session.refresh(job)
    assert job.status == "expired"


def test_run_once_processes_failed_jobs(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="failed", past_deadline=True)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 1
    session.refresh(job)
    assert job.status == "expired"


def test_run_once_processes_cancelled_jobs(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)
    job = _make_job(session, user, status="cancelled", past_deadline=True)
    session.commit()

    storage = FakeStorageClient()
    worker = CleanupWorker()
    count = worker.run_once(session, storage)

    assert count == 1
    session.refresh(job)
    assert job.status == "expired"


def test_orchestrator_stamps_deadline_on_completion(session, monkeypatch):
    """Integration: orchestrator stamps retention_deadline after job completion."""
    from app.domain.services.job_service import submit_job
    from app.queue.broker import InMemoryQueueBroker
    from app.worker.orchestrator import WorkerOrchestrator
    from app.db.models.user import UserCreditAccount

    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    user = _make_user(session)

    broker = InMemoryQueueBroker()
    job = submit_job(
        session=session, broker=broker, user_id=user.user_id,
        mode="translate", target_language="de", credit_estimate=0
    )
    session.commit()

    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-w")
    worker.process_one(session, broker, storage)

    session.refresh(job)
    assert job.status == "completed"
    assert job.retention_deadline is not None
