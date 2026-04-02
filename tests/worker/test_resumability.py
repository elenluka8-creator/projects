"""Tests for worker startup recovery and translation resumability.

Bug 1: On restart, job_runs with status='created' and parent job.status='queued'
       are re-enqueued from PostgreSQL, compensating for the ephemeral Redis queue.

Bug 2: When a job_run is resumed, completed translation batches are detected and
       skipped. The serialized TranslatedSegmentCollection is loaded from S3 rather
       than re-running the LLM for already-completed work.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — registers all models with Base.metadata
from app.db.base import Base
from app.pipeline.translation.consistency import ConsistencyMemory
from app.db.models.artifact import Artifact
from app.db.models.job import Job, JobRun
from app.db.models.translation_batch import TranslationBatch
from app.db.models.user import User, UserCreditAccount
from app.pipeline.segmentation.models import (
    BatchBoundaryHint,
    BatchPlanning,
    Segment,
    SegmentCollection,
)
from app.pipeline.translation.models import (
    TranslatedSegment,
    TranslatedSegmentCollection,
)
from app.storage.client import FakeStorageClient
from app.worker.lease import find_active_processing_runs, find_unqueued_created_runs
from app.worker.orchestrator import (
    WorkerOrchestrator,
    _deserialize_translated_collection,
    _serialize_translated_collection,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Exclude job_consistency_snapshots: its JSONB columns are PostgreSQL-only
    # and cannot be created in SQLite. ConsistencyRepository is mocked in tests
    # that reach the code path requiring it.
    tables = [
        t
        for t in Base.metadata.sorted_tables
        if t.name != "job_consistency_snapshots"
    ]
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_user(session) -> User:
    u = User(google_sub=f"sub-{uuid.uuid4()}", email="test@example.com")
    session.add(u)
    session.flush()
    account = UserCreditAccount(user_id=u.user_id, balance=1000)
    session.add(account)
    session.flush()
    return u


def _make_job_and_run(
    session,
    job_status: str = "queued",
    run_status: str = "created",
) -> tuple[Job, JobRun]:
    user = _make_user(session)
    job = Job(
        user_id=user.user_id,
        status=job_status,
        mode="translate",
        target_language="de",
    )
    session.add(job)
    session.flush()
    run = JobRun(
        job_id=job.job_id,
        user_id=user.user_id,
        status=run_status,
    )
    session.add(run)
    job.current_run_id = run.job_run_id
    session.flush()
    return job, run


def _make_segment_collection(n_batches: int = 2, estimate: int | None = None) -> SegmentCollection:
    """Build a minimal SegmentCollection with one segment per batch."""
    doc_id = uuid.uuid4()
    segments = []
    hints = []
    for i in range(n_batches):
        seg = Segment(
            id=f"seg-{i}",
            paragraph_id=f"seg-{i}",
            chapter_ref="ch-1",
            structural_ref=None,
            original_text=f"Text {i}",
            token_estimate=10,
        )
        segments.append(seg)
        hints.append(
            BatchBoundaryHint(
                batch_index=i,
                segment_ids=[seg.id],
                token_total=10,
                chapter_ref="ch-1",
            )
        )
    planning = BatchPlanning(
        chapter_boundaries={"ch-1": 0},
        batch_boundary_hints=hints,
        estimated_batch_count=estimate if estimate is not None else n_batches,
    )
    return SegmentCollection(
        document_id=doc_id,
        mode="translate",
        segments=segments,
        batch_planning=planning,
    )


def _make_translated_collection(doc_id: uuid.UUID, n_segs: int = 2) -> TranslatedSegmentCollection:
    segs = [
        TranslatedSegment(
            id=f"seg-{i}",
            paragraph_id=f"seg-{i}",
            chapter_ref="ch-1",
            structural_ref=None,
            original_text=f"Text {i}",
            translated_text=f"Übersetzung {i}",
            explanations=[],
        )
        for i in range(n_segs)
    ]
    return TranslatedSegmentCollection(
        document_id=doc_id,
        mode="translate",
        translated_segments=segs,
    )


def _add_translation_batches(
    session, job: Job, run: JobRun, n: int, status: str = "completed"
) -> None:
    for i in range(n):
        tb = TranslationBatch(
            job_run_id=run.job_run_id,
            job_id=job.job_id,
            batch_index=i,
            status=status,
        )
        session.add(tb)
    session.flush()


def _put_artifact(
    storage: FakeStorageClient,
    job: Job,
    run: JobRun,
    collection: TranslatedSegmentCollection,
) -> str:
    key = (
        f"users/{job.user_id}/jobs/{job.job_id}"
        f"/translation_artifacts/{run.job_run_id}/translated_collection.json"
    )
    storage.put_object_bytes(key, _serialize_translated_collection(collection))
    return key


# ── Bug 1 Tests ────────────────────────────────────────────────────────────────


def test_find_unqueued_created_runs_returns_orphaned_runs(session):
    """Runs with status='created' under a 'queued' job are returned."""
    job, run = _make_job_and_run(session, job_status="queued", run_status="created")
    session.commit()

    result = find_unqueued_created_runs(session)

    assert any(r.job_run_id == run.job_run_id for r in result)


def test_find_unqueued_created_runs_excludes_leased_processing(session):
    """Runs with status='leased' or 'processing' are excluded even if job is 'queued'."""
    _, run_leased = _make_job_and_run(session, job_status="queued", run_status="leased")
    _, run_processing = _make_job_and_run(session, job_status="queued", run_status="processing")
    session.commit()

    result = find_unqueued_created_runs(session)

    run_ids = {r.job_run_id for r in result}
    assert run_leased.job_run_id not in run_ids
    assert run_processing.job_run_id not in run_ids


def test_find_unqueued_created_runs_excludes_non_queued_jobs(session):
    """Runs with status='created' under a job that is NOT 'queued' are excluded."""
    _, run = _make_job_and_run(session, job_status="processing", run_status="created")
    session.commit()

    result = find_unqueued_created_runs(session)

    run_ids = {r.job_run_id for r in result}
    assert run.job_run_id not in run_ids


# ── FIX-9 Tests — active-lease orphan recovery ─────────────────────────────────


def test_find_active_processing_runs_returns_processing_with_active_lease(session):
    """Runs in 'processing' with a non-expired lease are returned for startup reset."""
    _, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    run.lease_expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
    session.commit()

    result = find_active_processing_runs(session)

    assert any(r.job_run_id == run.job_run_id for r in result)


def test_find_active_processing_runs_returns_leased_with_active_lease(session):
    """Runs in 'leased' with a non-expired lease are also returned."""
    _, run = _make_job_and_run(session, job_status="processing", run_status="leased")
    run.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    session.commit()

    result = find_active_processing_runs(session)

    assert any(r.job_run_id == run.job_run_id for r in result)


def test_find_active_processing_runs_excludes_expired_lease(session):
    """Runs with an expired lease are NOT returned — detect_expired_leases handles them."""
    _, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    run.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()

    result = find_active_processing_runs(session)

    run_ids = {r.job_run_id for r in result}
    assert run.job_run_id not in run_ids


def test_find_active_processing_runs_excludes_completed_and_created(session):
    """Runs in terminal or initial states are not returned."""
    _, run_created = _make_job_and_run(session, job_status="queued", run_status="created")
    _, run_completed = _make_job_and_run(session, job_status="completed", run_status="completed")
    session.commit()

    result = find_active_processing_runs(session)

    run_ids = {r.job_run_id for r in result}
    assert run_created.job_run_id not in run_ids
    assert run_completed.job_run_id not in run_ids


# ── Bug 2 Tests ────────────────────────────────────────────────────────────────


def test_translate_skipped_when_all_batches_complete_and_artifact_exists(session):
    """When all batches are 'completed' in DB and the artifact is in S3,
    _run_translate returns the loaded collection without calling the LLM provider."""
    job, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    n_batches = 3
    _add_translation_batches(session, job, run, n=n_batches, status="completed")
    session.commit()

    doc_id = uuid.uuid4()
    expected = _make_translated_collection(doc_id, n_segs=n_batches)
    storage = FakeStorageClient()
    _put_artifact(storage, job, run, expected)

    segment_collection = _make_segment_collection(n_batches=n_batches)
    worker = WorkerOrchestrator(worker_id="test-worker")

    with patch("app.worker.orchestrator.run_translation") as mock_translate:
        result = worker._run_translate(session, job, run, segment_collection, storage)

    assert result is not None
    assert result.document_id == doc_id
    assert len(result.translated_segments) == n_batches
    mock_translate.assert_not_called()


def test_translate_reruns_when_artifact_missing_and_all_batches_complete(session):
    """When all batches are completed but the S3 artifact is missing,
    _run_translate falls through and performs a full re-run."""
    job, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    n_batches = 2
    _add_translation_batches(session, job, run, n=n_batches, status="completed")
    session.commit()

    storage = FakeStorageClient()  # intentionally empty — no artifact
    segment_collection = _make_segment_collection(n_batches=n_batches)
    fake_translated = _make_translated_collection(segment_collection.document_id, n_segs=n_batches)

    worker = WorkerOrchestrator(worker_id="test-worker")

    with patch("app.worker.orchestrator.run_translation", return_value=fake_translated) as mock_translate:
        with patch("app.worker.orchestrator.AnthropicProvider"):
            with patch(
                "app.worker.orchestrator.ConsistencyRepository.load",
                return_value=ConsistencyMemory.empty(),
            ):
                result = worker._run_translate(session, job, run, segment_collection, storage)

    assert result is not None
    mock_translate.assert_called_once()


def test_translate_proceeds_when_partial_batches_complete(session):
    """When only M < N batches are completed, _run_translate does not skip."""
    job, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    n_total = 3
    n_done = 1
    _add_translation_batches(session, job, run, n=n_done, status="completed")
    session.commit()

    storage = FakeStorageClient()
    segment_collection = _make_segment_collection(n_batches=n_total)
    fake_translated = _make_translated_collection(segment_collection.document_id, n_segs=n_total)

    worker = WorkerOrchestrator(worker_id="test-worker")

    with patch("app.worker.orchestrator.run_translation", return_value=fake_translated) as mock_translate:
        with patch("app.worker.orchestrator.AnthropicProvider"):
            with patch(
                "app.worker.orchestrator.ConsistencyRepository.load",
                return_value=ConsistencyMemory.empty(),
            ):
                result = worker._run_translate(session, job, run, segment_collection, storage)

    assert result is not None
    mock_translate.assert_called_once()


def test_translate_persists_artifact_and_db_record_on_completion(session):
    """After a successful run_translation(), the result is written to S3 and
    an Artifact DB record is inserted."""
    job, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    session.commit()  # no existing batches

    storage = FakeStorageClient()
    segment_collection = _make_segment_collection(n_batches=1)
    fake_translated = _make_translated_collection(segment_collection.document_id, n_segs=1)

    worker = WorkerOrchestrator(worker_id="test-worker")

    with patch("app.worker.orchestrator.run_translation", return_value=fake_translated):
        with patch("app.worker.orchestrator.AnthropicProvider"):
            with patch(
                "app.worker.orchestrator.ConsistencyRepository.load",
                return_value=ConsistencyMemory.empty(),
            ):
                worker._run_translate(session, job, run, segment_collection, storage)

    expected_key = (
        f"users/{job.user_id}/jobs/{job.job_id}"
        f"/translation_artifacts/{run.job_run_id}/translated_collection.json"
    )

    # S3 artifact must be written and be deserializable
    stored_bytes = storage.get_object_bytes(expected_key)
    recovered = _deserialize_translated_collection(stored_bytes)
    assert recovered.document_id == fake_translated.document_id

    # Artifact DB record must be inserted
    artifact = (
        session.query(Artifact)
        .filter_by(job_id=job.job_id, artifact_type="translation_collection")
        .first()
    )
    assert artifact is not None
    assert artifact.object_key == expected_key
    assert artifact.storage_status == "active"


def test_total_batches_uses_db_count_not_estimate(session):
    """The skip threshold is based on the actual DB row count, not the planning
    estimate. If DB has N completed batches and the planning estimate says M > N,
    the run is still skipped when len(completed) >= N (the DB count)."""
    job, run = _make_job_and_run(session, job_status="processing", run_status="processing")
    n_actual = 2
    _add_translation_batches(session, job, run, n=n_actual, status="completed")
    session.commit()

    storage = FakeStorageClient()
    doc_id = uuid.uuid4()
    expected = _make_translated_collection(doc_id, n_segs=n_actual)
    _put_artifact(storage, job, run, expected)

    # Planning estimate deliberately diverges from actual DB count
    segment_collection = _make_segment_collection(n_batches=5, estimate=5)

    worker = WorkerOrchestrator(worker_id="test-worker")

    with patch("app.worker.orchestrator.run_translation") as mock_translate:
        result = worker._run_translate(session, job, run, segment_collection, storage)

    # Should skip because DB count (2) == completed count (2), regardless of estimate (5)
    assert result is not None
    assert result.document_id == doc_id
    mock_translate.assert_not_called()
