"""PreCheckResult — advisory pre-submission analysis stored per source artifact.

This is not a pipeline artifact (DEC-011).
Results are advisory; authoritative document metadata comes from the ingestion stage.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PRECHECK_STATUSES = frozenset({"pending", "completed", "failed"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PreCheckResult(Base):
    __tablename__ = "precheck_results"
    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_precheck_results_artifact_id"),
    )

    precheck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.artifact_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Populated on completed status
    detected_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    language_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_images: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Populated on completed status — advisory title/author from EPUB metadata
    book_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    book_author: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Populated on failed status
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
