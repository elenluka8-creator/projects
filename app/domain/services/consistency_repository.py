"""Persistence layer for ConsistencyMemory snapshots.

load()  — restore a job's consistency state from DB (returns empty if none).
save()  — upsert the current state after each translated batch.

One snapshot row per job_id; batch_index records progress for observability.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.job_consistency_snapshot import JobConsistencySnapshot
from app.pipeline.translation.consistency import ConsistencyMemory


class ConsistencyRepository:
    @staticmethod
    def load(session: Session, job_id: uuid.UUID) -> ConsistencyMemory:
        """Return the persisted ConsistencyMemory for this job, or an empty one."""
        snap = session.get(JobConsistencySnapshot, job_id)
        if snap is None:
            return ConsistencyMemory.empty()
        return ConsistencyMemory.from_snapshot_dict(
            {
                "terminology": snap.terminology or {},
                "entities": snap.entities or {},
                "chapter_summary": snap.chapter_summary or "",
            }
        )

    @staticmethod
    def save(
        session: Session,
        job_id: uuid.UUID,
        batch_index: int,
        memory: ConsistencyMemory,
    ) -> None:
        """Upsert the consistency snapshot. Caller must commit after this."""
        snap = session.get(JobConsistencySnapshot, job_id)
        data = memory.to_snapshot_dict()
        now = datetime.now(timezone.utc)

        if snap is None:
            snap = JobConsistencySnapshot(
                job_id=job_id,
                batch_index=batch_index,
                terminology=data["terminology"],
                entities=data["entities"],
                chapter_summary=data["chapter_summary"],
                updated_at=now,
            )
            session.add(snap)
        else:
            snap.batch_index = batch_index
            snap.terminology = data["terminology"]
            snap.entities = data["entities"]
            snap.chapter_summary = data["chapter_summary"]
            snap.updated_at = now

        session.flush()
