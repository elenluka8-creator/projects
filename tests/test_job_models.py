"""Unit tests for Job, JobRun, Document, TranslationBatch models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — ensures all models are registered with Base
from app.db.base import Base
from app.db.models.document import Document
from app.db.models.job import (
    FAILURE_CLASSES,
    JOB_ACTIVE_STATUSES,
    JOB_RUN_STATUSES,
    JOB_STATUSES,
    Job,
    JobRun,
)
from app.db.models.translation_batch import BATCH_STATUSES, TranslationBatch
from app.db.models.user import User, UserCreditAccount


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
    u = User(google_sub=f"sub-{uuid.uuid4()}", email="test@example.com")
    session.add(u)
    session.flush()
    account = UserCreditAccount(user_id=u.user_id, balance=1000)
    session.add(account)
    session.flush()
    return u


def test_job_status_constants():
    assert "queued" in JOB_STATUSES
    assert "processing" in JOB_ACTIVE_STATUSES
    assert "completed" not in JOB_ACTIVE_STATUSES
    assert "expired" not in JOB_ACTIVE_STATUSES


def test_job_run_status_constants():
    assert "leased" in JOB_RUN_STATUSES
    assert "completed" in JOB_RUN_STATUSES


def test_failure_class_constants():
    assert "content-deterministic" in FAILURE_CLASSES
    assert "policy" in FAILURE_CLASSES


def test_batch_statuses_constant():
    assert "completed" in BATCH_STATUSES
    assert "skipped" in BATCH_STATUSES


def test_job_creation(session):
    user = _make_user(session)
    job = Job(
        user_id=user.user_id,
        status="queued",
        mode="translate",
        target_language="de",
        credit_estimate=100,
    )
    session.add(job)
    session.flush()
    fetched = session.get(Job, job.job_id)
    assert fetched is not None
    assert fetched.status == "queued"
    assert fetched.mode == "translate"
    assert fetched.cancel_requested is False
    assert fetched.current_run_id is None


def test_job_run_creation(session):
    user = _make_user(session)
    job = Job(user_id=user.user_id, status="queued", mode="guided", target_language="fr")
    session.add(job)
    session.flush()

    run = JobRun(
        job_id=job.job_id,
        user_id=user.user_id,
        status="created",
        pipeline_version="0.1",
    )
    session.add(run)
    session.flush()

    fetched = session.get(JobRun, run.job_run_id)
    assert fetched is not None
    assert fetched.status == "created"
    assert fetched.worker_id is None
    assert fetched.lease_acquired_at is None


def test_document_creation(session):
    user = _make_user(session)
    job = Job(user_id=user.user_id, status="processing", mode="translate", target_language="es")
    session.add(job)
    session.flush()

    doc = Document(
        job_id=job.job_id,
        user_id=user.user_id,
        title="Test Book",
        author="Author",
        detected_language="en",
        detection_confidence=0.97,
        source_word_count=50000,
        chapter_count=12,
    )
    session.add(doc)
    session.flush()

    fetched = session.get(Document, doc.document_id)
    assert fetched is not None
    assert fetched.title == "Test Book"
    assert fetched.source_word_count == 50000
    assert fetched.detected_language == "en"


def test_translation_batch_creation(session):
    user = _make_user(session)
    job = Job(user_id=user.user_id, status="processing", mode="translate", target_language="de")
    session.add(job)
    session.flush()
    run = JobRun(job_id=job.job_id, user_id=user.user_id, status="processing")
    session.add(run)
    session.flush()

    batch = TranslationBatch(
        job_run_id=run.job_run_id,
        job_id=job.job_id,
        batch_index=0,
        chapter_ref="ch1",
        status="pending",
        tokens_in=1500,
        tokens_out=2000,
    )
    session.add(batch)
    session.flush()

    fetched = session.get(TranslationBatch, batch.batch_id)
    assert fetched is not None
    assert fetched.batch_index == 0
    assert fetched.tokens_in == 1500
    assert fetched.status == "pending"


def test_job_current_run_id_set(session):
    user = _make_user(session)
    job = Job(user_id=user.user_id, status="queued", mode="translate", target_language="ja")
    session.add(job)
    session.flush()
    run = JobRun(job_id=job.job_id, user_id=user.user_id, status="created")
    session.add(run)
    session.flush()

    job.current_run_id = run.job_run_id
    session.flush()

    fetched = session.get(Job, job.job_id)
    assert fetched.current_run_id == run.job_run_id
