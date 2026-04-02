"""Tests for retention policy — deadline stamping and window calculation."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.job import Job
from app.db.models.user import User, UserCreditAccount
from app.retention.policy import get_retention_window_days, stamp_retention_deadline


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


def _make_job(session, status: str = "completed") -> Job:
    user = User(google_sub=f"sub-{uuid.uuid4()}", email="r@example.com")
    session.add(user)
    session.flush()
    account = UserCreditAccount(user_id=user.user_id, balance=0)
    session.add(account)
    session.flush()
    job = Job(user_id=user.user_id, status=status, mode="translate", target_language="de")
    session.add(job)
    session.flush()
    return job


def test_get_retention_window_days_default(monkeypatch):
    monkeypatch.delenv("RETENTION_WINDOW_DAYS", raising=False)
    assert get_retention_window_days() == 30


def test_get_retention_window_days_from_env(monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "7")
    assert get_retention_window_days() == 7


def test_get_retention_window_days_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "bad")
    assert get_retention_window_days() == 30


def test_stamp_retention_deadline_sets_deadline(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    job = _make_job(session)
    terminal_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    stamp_retention_deadline(session, job, terminal_at=terminal_at)

    deadline = job.retention_deadline
    assert deadline is not None
    # deadline should be terminal_at + 30 days (compare as naive for SQLite)
    expected = terminal_at + timedelta(days=30)
    def naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    assert abs((naive(deadline) - naive(expected)).total_seconds()) < 1


def test_stamp_retention_deadline_idempotent(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    job = _make_job(session)
    terminal_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    stamp_retention_deadline(session, job, terminal_at=terminal_at)
    first_deadline = job.retention_deadline

    # Call again — should not change the deadline
    stamp_retention_deadline(session, job, terminal_at=terminal_at + timedelta(days=5))
    second_deadline = job.retention_deadline

    def naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    assert naive(first_deadline) == naive(second_deadline)


def test_stamp_retention_deadline_defaults_to_now(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "30")
    job = _make_job(session)
    before = datetime.now(timezone.utc)

    stamp_retention_deadline(session, job)

    after = datetime.now(timezone.utc)
    deadline = job.retention_deadline
    assert deadline is not None
    def naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    assert naive(before + timedelta(days=30)) <= naive(deadline)
    assert naive(deadline) <= naive(after + timedelta(days=30))


def test_stamp_retention_deadline_with_short_window(session, monkeypatch):
    monkeypatch.setenv("RETENTION_WINDOW_DAYS", "1")
    job = _make_job(session)
    terminal_at = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

    stamp_retention_deadline(session, job, terminal_at=terminal_at)

    def naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    expected = datetime(2026, 3, 16, 0, 0, 0)
    assert naive(job.retention_deadline) == expected
