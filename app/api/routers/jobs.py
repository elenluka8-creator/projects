"""Job API endpoints.

POST   /jobs                       — submit a new job (full config validation + idempotency)
GET    /jobs                       — list jobs for current user (with job-receipt fields)
GET    /jobs/{job_id}              — get a single job (with job-receipt fields)
GET    /jobs/{job_id}/download-url — issue a signed download URL for a completed job's output
POST   /jobs/{job_id}/cancel       — request cancellation
POST   /jobs/{job_id}/retry        — retry a failed job with the same source file
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import build_safe_error_detail
from app.config.policy import get_tier_model
from app.logging.structured import log_structured
from app.db.models.document import Document
from app.db.models.precheck import PreCheckResult
import logging
from app.db.models.job import Job
from app.db.session import get_db_session
from app.domain.services.credit_service import InsufficientCreditsError
from app.domain.services.job_service import (
    ActiveJobExistsError,
    InvalidJobConfigError,
    JobNotFoundError,
    JobRetryNotAllowedError,
    cancel_job,
    get_job,
    list_jobs,
    retry_failed_job,
    submit_job,
)
import os
from app.queue.broker import InMemoryQueueBroker, QueueBrokerProtocol, RedisQueueBroker
from app.storage.client import StorageClientProtocol, get_storage_client
from app.storage.service import issue_download_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Expiry for output download URLs (within the default policy window of 60-900 s)
_DOWNLOAD_URL_EXPIRY_SECONDS = 300


def get_queue_broker() -> QueueBrokerProtocol:
    """Return a RedisQueueBroker when REDIS_URL is set, InMemory otherwise.

    Tests override this via app.dependency_overrides and never reach this code,
    so the fallback keeps the test suite independent of Redis.
    """
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        return RedisQueueBroker(redis_url=redis_url)
    return InMemoryQueueBroker()


class SubmitJobRequest(BaseModel):
    mode: Literal["translate", "guided"]
    target_language: str
    source_language_override: Optional[str] = None
    translation_style: str = "natural"
    user_level: str = "B1"
    explanation_depth: str = "standard"
    quality_tier: Literal["express", "standard", "premium"] = "standard"
    source_artifact_id: Optional[uuid.UUID] = None
    word_count_estimate: Optional[int] = None
    credit_estimate: int = 0
    client_submission_id: Optional[uuid.UUID] = None
    ui_locale: Optional[str] = Field(None, max_length=5)


class JobResponse(BaseModel):
    job_id: str
    user_id: str
    status: str
    mode: str
    target_language: str
    source_language_override: Optional[str]
    translation_style: Optional[str]
    user_level: Optional[str]
    explanation_depth: Optional[str]
    client_submission_id: Optional[str]
    source_artifact_id: Optional[str]
    word_count_estimate: Optional[int]
    credit_estimate: Optional[int]
    failure_reason: Optional[str]
    failure_class: Optional[str]
    cancel_requested: bool
    created_at: str
    updated_at: str
    # Job-receipt fields (FEAT-JOBS)
    retention_deadline: Optional[str]
    retry_eligible: bool
    book_title: Optional[str]
    book_author: Optional[str]
    progress_percent: int = 0
    pipeline_stage: Optional[str] = None
    eta_seconds_remaining: Optional[int] = None
    processing_started_at: Optional[str] = None


class DownloadUrlResponse(BaseModel):
    job_id: str
    artifact_id: str
    download_url: str
    expires_in_seconds: int


def _job_to_response(
    job: Job,
    document: Optional[Document] = None,
    precheck: Optional[PreCheckResult] = None,
) -> JobResponse:
    now = datetime.now(timezone.utc)
    # Normalize timezone: SQLite returns naive datetimes; PostgreSQL returns aware.
    rd = job.retention_deadline
    if rd is not None and rd.tzinfo is None:
        rd = rd.replace(tzinfo=timezone.utc)
    retry_eligible = job.status == "failed" and (rd is None or rd > now)
    # Title/author: prefer authoritative Document (set after ingestion); fall back
    # to precheck advisory data which is available immediately after upload.
    book_title = (document.title if document else None) or (precheck.book_title if precheck else None)
    book_author = (document.author if document else None) or (precheck.book_author if precheck else None)
    return JobResponse(
        job_id=str(job.job_id),
        user_id=str(job.user_id),
        status=job.status,
        mode=job.mode,
        target_language=job.target_language,
        source_language_override=job.source_language_override,
        translation_style=job.translation_style,
        user_level=job.user_level,
        explanation_depth=job.explanation_depth,
        client_submission_id=(
            str(job.client_submission_id) if job.client_submission_id else None
        ),
        source_artifact_id=str(job.source_artifact_id) if job.source_artifact_id else None,
        word_count_estimate=job.word_count_estimate,
        credit_estimate=job.credit_estimate,
        failure_reason=job.failure_reason,
        failure_class=job.failure_class,
        cancel_requested=job.cancel_requested,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        retention_deadline=job.retention_deadline.isoformat() if job.retention_deadline else None,
        retry_eligible=retry_eligible,
        book_title=book_title,
        book_author=book_author,
        progress_percent=job.progress_percent,
        pipeline_stage=job.pipeline_stage,
        eta_seconds_remaining=job.eta_seconds_remaining,
        processing_started_at=(
            job.processing_started_at.isoformat() if job.processing_started_at else None
        ),
    )


def _fetch_documents_by_job_ids(
    session: Session, job_ids: List[uuid.UUID]
) -> Dict[uuid.UUID, Document]:
    """Batch-fetch Document records for a list of job IDs. Avoids N+1 queries."""
    if not job_ids:
        return {}
    rows = session.execute(
        select(Document).where(Document.job_id.in_(job_ids))
    ).scalars().all()
    return {doc.job_id: doc for doc in rows}


def _fetch_prechecks_by_artifact_ids(
    session: Session, artifact_ids: List[uuid.UUID]
) -> Dict[uuid.UUID, PreCheckResult]:
    """Batch-fetch completed PreCheckResult records for a list of source artifact IDs."""
    if not artifact_ids:
        return {}
    rows = session.execute(
        select(PreCheckResult).where(
            PreCheckResult.artifact_id.in_(artifact_ids),
            PreCheckResult.status == "completed",
        )
    ).scalars().all()
    return {pc.artifact_id: pc for pc in rows}


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    body: SubmitJobRequest,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    broker: QueueBrokerProtocol = Depends(get_queue_broker),
) -> JobResponse:
    """Submit a new job. Validates full config. Idempotent on client_submission_id."""
    try:
        job = submit_job(
            session=session,
            broker=broker,
            user_id=current_user_id,
            mode=body.mode,
            target_language=body.target_language,
            source_artifact_id=body.source_artifact_id,
            word_count_estimate=body.word_count_estimate,
            credit_estimate=body.credit_estimate,
            source_language_override=body.source_language_override,
            translation_style=body.translation_style,
            user_level=body.user_level,
            explanation_depth=body.explanation_depth,
            quality_tier=body.quality_tier,
            client_submission_id=body.client_submission_id,
            ui_locale=body.ui_locale,
        )
        session.commit()
    except InvalidJobConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_safe_error_detail(
                message=str(exc),
                context={"errors": exc.errors, "mode": body.mode},
            ),
        ) from exc
    except ActiveJobExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_safe_error_detail(
                message="User already has an active job.",
                context={"active_job_id": str(exc.active_job_id)},
            ),
        ) from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_safe_error_detail(
                message="Insufficient credits.",
                context={"required": exc.required, "available": exc.available},
            ),
        ) from exc
    # Emit tier analytics event (fire-and-forget — must not block submission)
    try:
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="analytics_event",
            payload={
                "event": "job_tier_selected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_id": str(job.job_id),
                "user_id": str(current_user_id),
                "quality_tier": body.quality_tier,
                "mode": body.mode,
                "target_language": body.target_language,
                "estimated_credits": body.credit_estimate,
                "model_name": get_tier_model(body.quality_tier),
            },
        )
    except Exception as exc:
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="job_tier_analytics_failed",
            payload={"error": type(exc).__name__},
        )
    # Document does not exist at submission time; use precheck for advisory title
    precheck: Optional[PreCheckResult] = None
    if job.source_artifact_id:
        precheck = session.execute(
            select(PreCheckResult).where(
                PreCheckResult.artifact_id == job.source_artifact_id,
                PreCheckResult.status == "completed",
            )
        ).scalar_one_or_none()
    return _job_to_response(job, document=None, precheck=precheck)


@router.get("", response_model=List[JobResponse])
def get_jobs(
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> List[JobResponse]:
    jobs = list_jobs(session=session, user_id=current_user_id)
    job_ids = [j.job_id for j in jobs]
    documents = _fetch_documents_by_job_ids(session, job_ids)
    artifact_ids = [j.source_artifact_id for j in jobs if j.source_artifact_id]
    prechecks = _fetch_prechecks_by_artifact_ids(session, artifact_ids)
    return [
        _job_to_response(
            j,
            document=documents.get(j.job_id),
            precheck=prechecks.get(j.source_artifact_id) if j.source_artifact_id else None,
        )
        for j in jobs
    ]


@router.get("/{job_id}/download-url", response_model=DownloadUrlResponse)
def get_download_url(
    job_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage_client: StorageClientProtocol = Depends(get_storage_client),
) -> DownloadUrlResponse:
    """Issue a short-lived signed download URL for the output EPUB of a completed job."""
    try:
        job = get_job(session=session, user_id=current_user_id, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id)},
            ),
        ) from exc

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_safe_error_detail(
                message="Job output is not yet available.",
                context={"job_id": str(job_id), "status": job.status},
            ),
        )

    if job.output_artifact_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="No output artifact found for this job.",
                context={"job_id": str(job_id)},
            ),
        )

    try:
        download_url = issue_download_url(
            session=session,
            client=storage_client,
            artifact_id=job.output_artifact_id,
            user_id=current_user_id,
            expires_in_seconds=_DOWNLOAD_URL_EXPIRY_SECONDS,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=build_safe_error_detail(
                message="Output artifact has been deleted or expired.",
                context={"job_id": str(job_id)},
            ),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Access denied.",
                context={"job_id": str(job_id)},
            ),
        ) from exc

    return DownloadUrlResponse(
        job_id=str(job_id),
        artifact_id=str(job.output_artifact_id),
        download_url=download_url,
        expires_in_seconds=_DOWNLOAD_URL_EXPIRY_SECONDS,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job_detail(
    job_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> JobResponse:
    try:
        job = get_job(session=session, user_id=current_user_id, job_id=job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id)},
            ),
        ) from exc
    document = session.execute(
        select(Document).where(Document.job_id == job_id)
    ).scalar_one_or_none()
    precheck: Optional[PreCheckResult] = None
    if job.source_artifact_id:
        precheck = session.execute(
            select(PreCheckResult).where(
                PreCheckResult.artifact_id == job.source_artifact_id,
                PreCheckResult.status == "completed",
            )
        ).scalar_one_or_none()
    return _job_to_response(job, document=document, precheck=precheck)


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job_endpoint(
    job_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> JobResponse:
    try:
        job = cancel_job(session=session, user_id=current_user_id, job_id=job_id)
        session.commit()
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id)},
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_safe_error_detail(
                message=str(exc),
                context={"job_id": str(job_id)},
            ),
        ) from exc
    # Document not needed for cancel response
    return _job_to_response(job, document=None)

@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_job(
    job_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    broker: QueueBrokerProtocol = Depends(get_queue_broker),
) -> JobResponse:
    """Create a new job from a failed job using the same source file (FEAT-ERROR-UX)."""
    try:
        job = retry_failed_job(
            session=session,
            broker=broker,
            user_id=current_user_id,
            failed_job_id=job_id,
        )
        session.commit()
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id)},
            ),
        ) from exc
    except JobRetryNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_safe_error_detail(
                message=exc.message,
                context={"job_id": str(job_id)},
            ),
        ) from exc
    except InvalidJobConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_safe_error_detail(
                message=str(exc),
                context={"errors": exc.errors, "job_id": str(job_id)},
            ),
        ) from exc
    except ActiveJobExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_safe_error_detail(
                message="You already have a job in progress. Wait for it to finish or cancel it.",
                context={"active_job_id": str(exc.active_job_id)},
            ),
        ) from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=build_safe_error_detail(
                message="Insufficient credits to retry.",
                context={"required": exc.required, "available": exc.available},
            ),
        ) from exc
    return _job_to_response(job, document=None)
