"""Job domain service.

Handles job submission, cancellation, and queries.
All state transitions emit timeline events via emit_timeline_event.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.policy import ConfigValidationError, validate_job_config
from app.db.models.job import JOB_ACTIVE_STATUSES, Job, JobRun
from app.domain.services.credit_service import InsufficientCreditsError, reserve_credits
from app.logging.structured import log_structured
from app.pipeline.version import PIPELINE_VERSION
from app.queue.broker import QueueBrokerProtocol
from app.telemetry.timeline import emit_timeline_event

logger = logging.getLogger(__name__)

# Idempotency deduplication window (POLICY-IDEMPOTENCY)
_IDEMPOTENCY_WINDOW_SECONDS = 60


class ActiveJobExistsError(Exception):
    """Raised when a user already has an active job (one-active-job rule)."""

    def __init__(self, user_id: uuid.UUID, active_job_id: uuid.UUID) -> None:
        super().__init__(
            f"User {user_id} already has an active job: {active_job_id}"
        )
        self.user_id = user_id
        self.active_job_id = active_job_id


class JobNotFoundError(Exception):
    """Raised when a job does not exist or is not owned by the caller."""


class InvalidJobConfigError(Exception):
    """Raised when job configuration parameters are invalid.

    `errors` contains one entry per policy violation (may be multiple).
    """

    def __init__(self, message: str, errors: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.errors = errors or [message]


def submit_job(
    session: Session,
    broker: QueueBrokerProtocol,
    user_id: uuid.UUID,
    mode: str,
    target_language: str,
    *,
    source_artifact_id: Optional[uuid.UUID] = None,
    word_count_estimate: Optional[int] = None,
    credit_estimate: int = 0,
    source_language_override: Optional[str] = None,
    translation_style: str = "natural",
    user_level: str = "B1",
    explanation_depth: str = "standard",
    quality_tier: str = "standard",
    client_submission_id: Optional[uuid.UUID] = None,
    ui_locale: Optional[str] = None,
) -> Job:
    """Submit a new job: validate config, check idempotency, reserve credits, enqueue.

    Enforces:
    - Full config validation (mode, languages, style, level, depth)
    - One-active-job-per-user rule
    - POLICY-IDEMPOTENCY: same client_submission_id within 60s → return existing job
    - Credit reservation before enqueuing

    Raises:
        InvalidJobConfigError: one or more config violations.
        ActiveJobExistsError: user already has an active job.
        InsufficientCreditsError: insufficient credit balance.
    """
    # Full config validation (replaces bare mode check)
    try:
        validate_job_config(
            mode=mode,
            target_language=target_language,
            translation_style=translation_style,
            user_level=user_level,
            explanation_depth=explanation_depth,
            source_language=source_language_override,
            quality_tier=quality_tier,
        )
    except ConfigValidationError as exc:
        raise InvalidJobConfigError(str(exc), errors=exc.errors) from exc

    # Idempotency check (POLICY-IDEMPOTENCY)
    if client_submission_id is not None:
        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=_IDEMPOTENCY_WINDOW_SECONDS
        )
        existing = session.execute(
            select(Job).where(
                Job.user_id == user_id,
                Job.client_submission_id == client_submission_id,
                Job.created_at >= window_start,
            )
        ).scalar_one_or_none()
        if existing is not None:
            log_structured(
                logger=logger,
                level=logging.INFO,
                message="job_submit_idempotent",
                payload={
                    "job_id": str(existing.job_id),
                    "user_id": str(user_id),
                    "client_submission_id": str(client_submission_id),
                },
            )
            return existing

    _check_one_active_job(session, user_id)

    job = Job(
        user_id=user_id,
        status="queued",
        mode=mode,
        target_language=target_language,
        source_language_override=source_language_override,
        translation_style=translation_style,
        user_level=user_level,
        explanation_depth=explanation_depth if mode == "guided" else None,
        quality_tier=quality_tier if quality_tier else "standard",
        client_submission_id=client_submission_id,
        source_artifact_id=source_artifact_id,
        word_count_estimate=word_count_estimate,
        credit_estimate=credit_estimate,
        ui_locale=ui_locale,
    )
    session.add(job)
    session.flush()

    run = JobRun(
        job_id=job.job_id,
        user_id=user_id,
        status="created",
        pipeline_version=PIPELINE_VERSION,
    )
    session.add(run)
    session.flush()

    job.current_run_id = run.job_run_id
    session.flush()

    if credit_estimate > 0:
        reserve_credits(
            session=session,
            user_id=user_id,
            job_id=job.job_id,
            job_run_id=run.job_run_id,
            amount=credit_estimate,
        )

    emit_timeline_event(
        session=session,
        job_id=job.job_id,
        event_type="job_created",
        job_run_id=run.job_run_id,
        user_id=user_id,
    )

    if credit_estimate > 0:
        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="credit_reserved",
            job_run_id=run.job_run_id,
            user_id=user_id,
        )

    emit_timeline_event(
        session=session,
        job_id=job.job_id,
        event_type="job_queued",
        job_run_id=run.job_run_id,
        user_id=user_id,
    )

    broker.enqueue(run.job_run_id)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="job_submitted",
        payload={
            "job_id": str(job.job_id),
            "job_run_id": str(run.job_run_id),
            "user_id": str(user_id),
            "mode": mode,
            "target_language": target_language,
            "translation_style": translation_style,
            "user_level": user_level,
            "credit_estimate": credit_estimate,
        },
    )
    return job


def cancel_job(
    session: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> Job:
    """Request cancellation of an active job."""
    job = _get_owned_job(session, user_id, job_id)

    if job.status not in JOB_ACTIVE_STATUSES:
        raise ValueError(
            f"Cannot cancel job {job_id}: current status is '{job.status}' (terminal)."
        )

    job.cancel_requested = True
    session.flush()

    emit_timeline_event(
        session=session,
        job_id=job.job_id,
        event_type="cancel_requested",
        job_run_id=job.current_run_id,
        user_id=user_id,
    )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="job_cancel_requested",
        payload={"job_id": str(job_id), "user_id": str(user_id)},
    )
    return job


def get_job(session: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    """Return a job owned by user_id."""
    return _get_owned_job(session, user_id, job_id)


def list_jobs(session: Session, user_id: uuid.UUID) -> List[Job]:
    """Return all jobs owned by user_id, newest first."""
    result = session.execute(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())


def _check_one_active_job(session: Session, user_id: uuid.UUID) -> None:
    existing = session.execute(
        select(Job).where(
            Job.user_id == user_id,
            Job.status.in_(list(JOB_ACTIVE_STATUSES)),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ActiveJobExistsError(user_id=user_id, active_job_id=existing.job_id)


def _get_owned_job(session: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise JobNotFoundError(f"Job {job_id} not found for user {user_id}")
    return job


class JobRetryNotAllowedError(Exception):
    """Raised when a failed job cannot be retried with the same source file."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def retry_failed_job(
    session: Session,
    broker: QueueBrokerProtocol,
    user_id: uuid.UUID,
    failed_job_id: uuid.UUID,
) -> Job:
    """Create a new job reusing config and source artifact from a failed job.

    Eligibility (FEAT-ERROR-UX):
    - Job status is ``failed``
    - Retention deadline not passed (same rule as ``retry_eligible`` on API)
    - Source artifact exists, owned by user, and still stored
    """
    from app.db.models.artifact import Artifact

    job = _get_owned_job(session, user_id, failed_job_id)
    now = datetime.now(timezone.utc)
    if job.status != "failed":
        raise JobRetryNotAllowedError("Only failed jobs can be retried.")

    rd = job.retention_deadline
    if rd is not None:
        if rd.tzinfo is None:
            rd = rd.replace(tzinfo=timezone.utc)
        if rd <= now:
            raise JobRetryNotAllowedError(
                "The retry window has expired. Please upload the book again."
            )

    if job.source_artifact_id is None:
        raise JobRetryNotAllowedError("This job has no source file to retry with.")

    art = session.get(Artifact, job.source_artifact_id)
    if art is None or art.user_id != user_id:
        raise JobRetryNotAllowedError("The source file is no longer available.")
    if art.deleted_at is not None or art.storage_status != "active":
        raise JobRetryNotAllowedError("The source file is no longer available.")

    return submit_job(
        session=session,
        broker=broker,
        user_id=user_id,
        mode=job.mode,
        target_language=job.target_language,
        source_artifact_id=job.source_artifact_id,
        word_count_estimate=job.word_count_estimate,
        credit_estimate=job.credit_estimate or 0,
        source_language_override=job.source_language_override,
        translation_style=job.translation_style or "natural",
        user_level=job.user_level or "B1",
        explanation_depth=job.explanation_depth or "standard",
        client_submission_id=uuid.uuid4(),
    )
