"""Unit tests for the job domain service."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.job import Job
from app.db.models.user import User, UserCreditAccount
from app.domain.services.credit_service import InsufficientCreditsError
from app.domain.services.job_service import (
    ActiveJobExistsError,
    InvalidJobConfigError,
    JobNotFoundError,
    cancel_job,
    get_job,
    list_jobs,
    submit_job,
)
from app.queue.broker import InMemoryQueueBroker


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
    u = User(google_sub=f"sub-{uuid.uuid4()}", email="t@example.com")
    session.add(u)
    session.flush()
    account = UserCreditAccount(user_id=u.user_id, balance=balance)
    session.add(account)
    session.flush()
    return u


def _submit(session, broker, user, **kwargs):
    defaults = dict(mode="translate", target_language="de")
    defaults.update(kwargs)
    return submit_job(session=session, broker=broker, user_id=user.user_id, **defaults)


def test_submit_job_creates_job_and_run(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)

    assert job.status == "queued"
    assert job.mode == "translate"
    assert job.current_run_id is not None
    assert broker.queue_length() == 1


def test_submit_job_enqueues_run_id(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)
    dequeued = broker.dequeue()

    assert dequeued == job.current_run_id


def test_submit_job_reserves_credits(session):
    user = _make_user(session, balance=500)
    broker = InMemoryQueueBroker()

    _submit(session, broker, user, credit_estimate=200)

    account = session.query(UserCreditAccount).filter_by(user_id=user.user_id).one()
    assert account.balance == 300


def test_submit_job_blocks_second_active_job(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    _submit(session, broker, user, credit_estimate=0)

    with pytest.raises(ActiveJobExistsError):
        _submit(session, broker, user, credit_estimate=0)


def test_submit_job_invalid_mode(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    with pytest.raises(InvalidJobConfigError):
        submit_job(
            session=session,
            broker=broker,
            user_id=user.user_id,
            mode="invalid-mode",
            target_language="de",
        )


def test_submit_job_insufficient_credits(session):
    user = _make_user(session, balance=10)
    broker = InMemoryQueueBroker()

    with pytest.raises(InsufficientCreditsError):
        _submit(session, broker, user, credit_estimate=100)


def test_cancel_job_sets_flag(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)
    cancelled = cancel_job(session=session, user_id=user.user_id, job_id=job.job_id)

    assert cancelled.cancel_requested is True


def test_cancel_terminal_job_raises(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)
    job.status = "completed"
    session.flush()

    with pytest.raises(ValueError):
        cancel_job(session=session, user_id=user.user_id, job_id=job.job_id)


def test_cancel_job_not_owned(session):
    user = _make_user(session)
    other_user_id = uuid.uuid4()
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)

    with pytest.raises(JobNotFoundError):
        cancel_job(session=session, user_id=other_user_id, job_id=job.job_id)


def test_get_job_returns_owned(session):
    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)
    fetched = get_job(session=session, user_id=user.user_id, job_id=job.job_id)

    assert fetched.job_id == job.job_id


def test_get_job_not_found(session):
    user = _make_user(session)
    with pytest.raises(JobNotFoundError):
        get_job(session=session, user_id=user.user_id, job_id=uuid.uuid4())


def test_list_jobs_returns_user_jobs(session):
    user = _make_user(session, balance=10000)
    broker = InMemoryQueueBroker()

    _submit(session, broker, user, credit_estimate=0)
    # Complete first job to allow second
    first = list_jobs(session, user.user_id)[0]
    first.status = "completed"
    session.flush()

    _submit(session, broker, user, credit_estimate=0)

    jobs = list_jobs(session=session, user_id=user.user_id)
    assert len(jobs) == 2


def test_list_jobs_empty_for_unknown_user(session):
    jobs = list_jobs(session=session, user_id=uuid.uuid4())
    assert jobs == []


def test_submit_job_emits_timeline_events(session):
    from app.db.models.job_event import JobEvent

    user = _make_user(session)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=0)

    events = session.query(JobEvent).filter_by(job_id=job.job_id).all()
    event_types = {e.event_type for e in events}

    assert "job_created" in event_types
    assert "job_queued" in event_types


def test_submit_job_with_credits_emits_credit_reserved_event(session):
    from app.db.models.job_event import JobEvent

    user = _make_user(session, balance=500)
    broker = InMemoryQueueBroker()

    job = _submit(session, broker, user, credit_estimate=100)

    events = session.query(JobEvent).filter_by(job_id=job.job_id).all()
    event_types = {e.event_type for e in events}
    assert "credit_reserved" in event_types
