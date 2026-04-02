"""Job and JobRun SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

JOB_STATUSES = frozenset(
    {"validating", "queued", "processing", "completed", "failed", "cancelled", "expired"}
)

JOB_ACTIVE_STATUSES = frozenset({"validating", "queued", "processing"})

JOB_RUN_STATUSES = frozenset(
    {"created", "leased", "processing", "completed", "failed", "cancelled"}
)

FAILURE_CLASSES = frozenset(
    {"provider-transient", "content-deterministic", "system", "policy"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    target_language: Mapped[str] = mapped_column(String, nullable=False)
    source_language_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Config fields (FEAT-CONFIG)
    translation_style: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    user_level: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    explanation_depth: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Idempotency key (POLICY-IDEMPOTENCY)
    client_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    source_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    output_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # No FK constraint — avoids circular dependency with job_runs
    current_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    word_count_estimate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    credit_estimate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    failure_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retention_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quality_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ui_locale: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pipeline_stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    eta_seconds_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    job_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    pipeline_version: Mapped[str] = mapped_column(String, nullable=False, default="0.1")
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider_config_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lease_acquired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    failure_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
