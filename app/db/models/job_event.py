from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TIMELINE_EVENT_TYPES = frozenset(
    {
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
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobEvent(Base):
    __tablename__ = "job_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # job_id has no FK yet — jobs table is added in FEAT-QUEUE
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    job_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # user_id is a correlation field only — no FK until we need it
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    batch_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # payload is metadata-only; sanitized before insert (no raw book text)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
