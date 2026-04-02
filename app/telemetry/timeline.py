from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Literal, Optional

from sqlalchemy.orm import Session

from app.db.models.job_event import TIMELINE_EVENT_TYPES, JobEvent
from app.logging.structured import log_structured
from app.security.payload_guard import sanitize_for_logging_payload

logger = logging.getLogger(__name__)

TimelineEventType = Literal[
    "job_created",
    "job_validated",
    "job_queued",
    "credit_reserved",
    "job_run_created",
    "job_run_leased",
    "job_processing_started",
    "batch_started",
    "batch_completed",
    "batch_failed",
    "retry_scheduled",
    "cancel_requested",
    "job_cancelled",
    "credit_consumed",
    "credit_refunded",
    "job_completed",
    "job_failed",
    "cleanup_started",
    "cleanup_completed",
    "job_expired",
    "preamble_analyzed",
]


def emit_timeline_event(
    session: Session,
    job_id: uuid.UUID,
    event_type: TimelineEventType,
    *,
    job_run_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    stage: Optional[str] = None,
    batch_index: Optional[int] = None,
    provider: Optional[str] = None,
    error_class: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> JobEvent:
    """Insert a durable timeline event record and emit a structured log entry.

    `payload` is always sanitized via `sanitize_for_logging_payload` before
    any DB insert or log emission — this is the only write path and callers
    cannot bypass the no-raw-text rule.

    Args:
        session: SQLAlchemy session (caller responsible for commit).
        job_id: The job this event belongs to.
        event_type: One of the 20 DEC-008 event types.
        job_run_id: Optional run identifier for events within a specific run.
        user_id: Optional user identifier for correlation.
        stage: Optional pipeline stage name.
        batch_index: Optional batch index within the run.
        provider: Optional LLM provider identifier.
        error_class: Optional error class for failure events.
        payload: Optional metadata dict (token counts, latency, etc.).
            Must not contain raw book text — will be sanitized unconditionally.

    Returns:
        The created JobEvent (not yet committed to DB).

    Raises:
        ValueError: if event_type is not a known timeline event type.
    """
    if event_type not in TIMELINE_EVENT_TYPES:
        raise ValueError(
            f"Unknown timeline event type '{event_type}'. "
            f"Must be one of: {sorted(TIMELINE_EVENT_TYPES)}"
        )

    safe_payload = sanitize_for_logging_payload(payload or {}) or None

    event = JobEvent(
        job_id=job_id,
        event_type=event_type,
        job_run_id=job_run_id,
        user_id=user_id,
        stage=stage,
        batch_index=batch_index,
        provider=provider,
        error_class=error_class,
        payload=safe_payload if safe_payload else None,
    )
    session.add(event)
    session.flush()

    log_record: Dict[str, Any] = {
        "event_type": event_type,
        "job_id": str(job_id),
    }
    if job_run_id is not None:
        log_record["job_run_id"] = str(job_run_id)
    if user_id is not None:
        log_record["user_id"] = str(user_id)
    if stage is not None:
        log_record["stage"] = stage
    if batch_index is not None:
        log_record["batch_index"] = batch_index
    if provider is not None:
        log_record["provider"] = provider
    if error_class is not None:
        log_record["error_class"] = error_class

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="timeline_event",
        payload=log_record,
    )

    return event
