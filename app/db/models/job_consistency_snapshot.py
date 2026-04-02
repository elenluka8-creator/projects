"""DB model for job consistency memory snapshots.

One row per job — upserted after each translated batch so state survives
worker restarts without losing the entire consistency history.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobConsistencySnapshot(Base):
    __tablename__ = "job_consistency_snapshots"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    batch_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminology: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    entities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    chapter_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
