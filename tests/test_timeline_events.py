from __future__ import annotations

import logging
import uuid
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — registers all models with Base
from app.db.base import Base
from app.db.models.job_event import TIMELINE_EVENT_TYPES, JobEvent
from app.security.payload_guard import REDACTION_MARKER
from app.telemetry.timeline import TimelineEventType, emit_timeline_event


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_all_20_event_types_are_defined() -> None:
    assert len(TIMELINE_EVENT_TYPES) == 20


def test_emit_timeline_event_creates_db_record(db_session) -> None:
    job_id = uuid4()
    user_id = uuid4()

    event = emit_timeline_event(
        session=db_session,
        job_id=job_id,
        event_type="job_created",
        user_id=user_id,
    )
    db_session.commit()

    record = db_session.get(JobEvent, event.event_id)
    assert record is not None
    assert record.job_id == job_id
    assert record.event_type == "job_created"
    assert record.user_id == user_id


def test_emit_timeline_event_stores_all_optional_fields(db_session) -> None:
    job_id = uuid4()
    job_run_id = uuid4()
    user_id = uuid4()

    event = emit_timeline_event(
        session=db_session,
        job_id=job_id,
        event_type="batch_started",
        job_run_id=job_run_id,
        user_id=user_id,
        stage="translation",
        batch_index=3,
        provider="openai",
        payload={"token_count": 512, "latency_ms": 1200},
    )
    db_session.commit()

    record = db_session.get(JobEvent, event.event_id)
    assert record.job_run_id == job_run_id
    assert record.stage == "translation"
    assert record.batch_index == 3
    assert record.provider == "openai"
    assert record.payload is not None
    assert record.payload["token_count"] == 512


def test_emit_timeline_event_sanitizes_payload(db_session) -> None:
    job_id = uuid4()

    event = emit_timeline_event(
        session=db_session,
        job_id=job_id,
        event_type="batch_completed",
        payload={
            "token_count": 256,
            "source_text": "This is raw book content that must not be stored",
        },
    )
    db_session.commit()

    record = db_session.get(JobEvent, event.event_id)
    assert record.payload is not None
    assert record.payload["token_count"] == 256
    assert record.payload["source_text"] == REDACTION_MARKER


def test_emit_timeline_event_rejects_unknown_event_type(db_session) -> None:
    with pytest.raises(ValueError, match="Unknown timeline event type"):
        emit_timeline_event(
            session=db_session,
            job_id=uuid4(),
            event_type="nonexistent_event",  # type: ignore[arg-type]
        )


def test_emit_timeline_event_emits_structured_log(
    db_session, caplog: pytest.LogCaptureFixture
) -> None:
    job_id = uuid4()

    with caplog.at_level(logging.INFO, logger="app.telemetry.timeline"):
        emit_timeline_event(
            session=db_session,
            job_id=job_id,
            event_type="job_completed",
        )

    assert any("timeline_event" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "timeline_event" in r.message)
    assert record.__dict__.get("event_type") == "job_completed"
    assert record.__dict__.get("job_id") == str(job_id)


def test_emit_timeline_event_stores_all_20_types(db_session) -> None:
    job_id = uuid4()
    for event_type in TIMELINE_EVENT_TYPES:
        emit_timeline_event(
            session=db_session,
            job_id=job_id,
            event_type=event_type,  # type: ignore[arg-type]
        )
    db_session.commit()

    from sqlalchemy import select
    results = db_session.execute(
        select(JobEvent).where(JobEvent.job_id == job_id)
    ).scalars().all()
    stored_types = {r.event_type for r in results}
    assert stored_types == TIMELINE_EVENT_TYPES


def test_emit_timeline_event_stores_error_class(db_session) -> None:
    event = emit_timeline_event(
        session=db_session,
        job_id=uuid4(),
        event_type="job_failed",
        error_class="provider_timeout",
    )
    db_session.commit()

    record = db_session.get(JobEvent, event.event_id)
    assert record.error_class == "provider_timeout"


def test_emit_timeline_event_empty_payload_stores_none(db_session) -> None:
    event = emit_timeline_event(
        session=db_session,
        job_id=uuid4(),
        event_type="job_queued",
    )
    db_session.commit()

    record = db_session.get(JobEvent, event.event_id)
    assert record.payload is None
