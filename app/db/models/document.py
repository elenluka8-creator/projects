"""Document SQLAlchemy model.

Stores the normalized metadata produced by the ingestion stage.
This is the authoritative source for cost estimation, batch planning,
and progress weight calculations (DEC-009).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="epub")
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False)
    detected_language: Mapped[str] = mapped_column(String, nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    user_language_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_batch_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
