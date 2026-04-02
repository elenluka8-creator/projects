"""Tests for worker orchestrator and lease management."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.job import Job, JobRun
from app.db.models.user import User, UserCreditAccount
from app.domain.services.job_service import submit_job
from app.queue.broker import InMemoryQueueBroker
from app.storage.client import FakeStorageClient
from app.worker.lease import acquire_lease, detect_expired_leases, release_lease, renew_lease
from app.worker.orchestrator import WorkerOrchestrator


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


def _make_user(session, balance: int = 1000) -> User:
    u = User(google_sub=f"sub-{uuid.uuid4()}", email="w@example.com")
    session.add(u)
    session.flush()
    account = UserCreditAccount(user_id=u.user_id, balance=balance)
    session.add(account)
    session.flush()
    return u


def _submit_job(session, broker, user, **kwargs):
    return submit_job(
        session=session,
        broker=broker,
        user_id=user.user_id,
        mode="translate",
        target_language="de",
        **kwargs,
    )


# --- Lease tests ---

def test_acquire_lease_succeeds_for_created_run(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    result = acquire_lease(session, run_id, "worker-1", duration_seconds=300)

    assert result is True
    run = session.get(JobRun, run_id)
    assert run.status == "leased"
    assert run.worker_id == "worker-1"
    assert run.lease_expires_at is not None


def test_acquire_lease_fails_for_already_leased_run(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    acquire_lease(session, run_id, "worker-1")
    result = acquire_lease(session, run_id, "worker-2")

    assert result is False


def test_acquire_lease_fails_for_nonexistent_run(session):
    result = acquire_lease(session, uuid.uuid4(), "worker-1")
    assert result is False


def test_renew_lease_extends_expiry(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    acquire_lease(session, run_id, "worker-1", duration_seconds=10)

    run_before = session.get(JobRun, run_id)
    old_expiry = run_before.lease_expires_at

    renew_lease(session, run_id, "worker-1", duration_seconds=300)

    run_after = session.get(JobRun, run_id)
    # Strip tzinfo for SQLite comparison (SQLite returns naive datetimes on reload)
    def _naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    assert _naive(run_after.lease_expires_at) > _naive(old_expiry)


def test_renew_lease_fails_for_wrong_worker(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    acquire_lease(session, run_id, "worker-1")

    result = renew_lease(session, run_id, "wrong-worker")
    assert result is False


def test_release_lease_clears_worker(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    acquire_lease(session, run_id, "worker-1")
    release_lease(session, run_id, "worker-1")

    run = session.get(JobRun, run_id)
    assert run.worker_id is None
    assert run.lease_expires_at is None


def test_detect_expired_leases_finds_expired(session):
    from datetime import datetime, timedelta, timezone

    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    run_id = job.current_run_id
    acquire_lease(session, run_id, "worker-1", duration_seconds=300)

    run = session.get(JobRun, run_id)
    run.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.flush()

    expired = detect_expired_leases(session)
    assert any(r.job_run_id == run_id for r in expired)


# --- Orchestrator tests ---

def test_process_one_returns_false_when_empty(session):
    broker = InMemoryQueueBroker()
    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-worker")

    result = worker.process_one(session, broker, storage)
    assert result is False


def test_process_one_completes_job_without_artifact(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-worker")

    result = worker.process_one(session, broker, storage)
    assert result is True

    session.refresh(job)
    assert job.status == "completed"


def test_process_one_emits_timeline_events(session):
    from app.db.models.job_event import JobEvent

    user = _make_user(session)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=0)
    session.commit()

    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-worker")
    worker.process_one(session, broker, storage)

    events = session.query(JobEvent).filter_by(job_id=job.job_id).all()
    event_types = {e.event_type for e in events}

    assert "job_run_leased" in event_types
    assert "job_processing_started" in event_types
    assert "job_completed" in event_types


def test_process_one_handles_cancellation(session):
    user = _make_user(session, balance=500)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=100)
    session.commit()

    job.cancel_requested = True
    session.commit()

    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-worker")
    worker.process_one(session, broker, storage)

    session.refresh(job)
    assert job.status == "cancelled"

    account = session.query(UserCreditAccount).filter_by(user_id=user.user_id).one()
    assert account.balance == 500


def test_process_one_settles_credits_on_completion(session):
    user = _make_user(session, balance=500)
    broker = InMemoryQueueBroker()
    job = _submit_job(session, broker, user, credit_estimate=100)
    session.commit()

    storage = FakeStorageClient()
    worker = WorkerOrchestrator(worker_id="test-worker")
    worker.process_one(session, broker, storage)

    from app.db.models.user import CreditTransaction
    txns = session.query(CreditTransaction).filter_by(user_id=user.user_id).all()
    tx_types = {t.type for t in txns}
    assert "reservation" in tx_types
    assert "consumption" in tx_types
    assert "refund" not in tx_types

    session.refresh(job)
    assert job.status == "completed"


def test_queue_broker_in_memory_enqueue_dequeue():
    broker = InMemoryQueueBroker()
    run_id = uuid.uuid4()
    broker.enqueue(run_id)
    assert broker.queue_length() == 1
    dequeued = broker.dequeue()
    assert dequeued == run_id
    assert broker.queue_length() == 0
    assert broker.dequeue() is None
