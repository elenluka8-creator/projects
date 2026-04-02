"""Cleanup worker for job content lifecycle.

CleanupWorker.run_once() scans for terminal jobs past their retention deadline,
deletes their content-bearing artifacts, and transitions them to `expired`.

Design rules (ARCH §Cleanup Flow):
  - idempotent: safe to run multiple times
  - must not delete artifacts for jobs with an active job_run
  - emits cleanup_started, cleanup_completed, job_expired timeline events
  - storage deletion errors on already-deleted objects are logged, not raised
  - DB metadata (artifacts, jobs) is retained after content deletion
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.artifact import Artifact
from app.db.models.job import Job, JobRun
from app.logging.structured import log_structured
from app.storage.client import StorageClientProtocol
from app.storage.service import mark_artifact_deleted
from app.telemetry.timeline import emit_timeline_event

logger = logging.getLogger(__name__)


class CleanupWorker:
    """Scheduled cleanup worker for content artifact deletion."""

    def run_once(
        self,
        session: Session,
        storage_client: StorageClientProtocol,
    ) -> int:
        """Run one cleanup pass.

        Finds all terminal jobs past their retention_deadline, deletes their
        content artifacts, and marks them as expired.

        Returns:
            Number of jobs processed (expired) in this pass.
        """
        now = datetime.now(timezone.utc)
        eligible_jobs = self._find_eligible_jobs(session, now)

        expired_count = 0
        for job in eligible_jobs:
            try:
                processed = self._process_job(session, storage_client, job)
                if processed:
                    expired_count += 1
            except Exception as exc:
                log_structured(
                    logger=logger,
                    level=logging.ERROR,
                    message="cleanup_job_error",
                    payload={
                        "job_id": str(job.job_id),
                        "error": str(exc)[:500],
                    },
                )
                session.rollback()

        return expired_count

    def _find_eligible_jobs(self, session: Session, now: datetime) -> List[Job]:
        """Return terminal jobs whose retention_deadline has passed."""
        terminal_statuses = ("completed", "failed", "cancelled")
        # Compare as naive UTC for SQLite compatibility
        now_naive = now.replace(tzinfo=None) if now.tzinfo else now

        rows = session.execute(
            select(Job).where(
                Job.status.in_(terminal_statuses),
                Job.retention_deadline != None,  # noqa: E711
            )
        ).scalars().all()

        # Filter in Python to handle SQLite naive vs. aware comparison safely
        result = []
        for job in rows:
            deadline = job.retention_deadline
            if deadline is None:
                continue
            deadline_naive = deadline.replace(tzinfo=None) if deadline.tzinfo else deadline
            if deadline_naive <= now_naive:
                result.append(job)
        return result

    def _process_job(
        self,
        session: Session,
        storage_client: StorageClientProtocol,
        job: Job,
    ) -> bool:
        """Process one job's retention cleanup.

        Returns True if the job was successfully expired.
        Returns False if the job was skipped (active run detected).
        """
        # Safety: skip if there is an active job_run
        active_run = session.execute(
            select(JobRun).where(
                JobRun.job_id == job.job_id,
                JobRun.status.in_(["leased", "processing"]),
            )
        ).scalar_one_or_none()

        if active_run is not None:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="cleanup_skipped_active_run",
                payload={
                    "job_id": str(job.job_id),
                    "job_run_id": str(active_run.job_run_id),
                },
            )
            return False

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="cleanup_started",
            user_id=job.user_id,
        )
        session.flush()

        artifacts = session.execute(
            select(Artifact).where(
                Artifact.job_id == job.job_id,
                Artifact.storage_status == "active",
            )
        ).scalars().all()

        deleted_count = 0
        for artifact in artifacts:
            deleted = self._delete_artifact(session, storage_client, artifact)
            if deleted:
                deleted_count += 1

        job.status = "expired"
        session.flush()

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="cleanup_completed",
            user_id=job.user_id,
            payload={"deleted_artifact_count": deleted_count},
        )
        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_expired",
            user_id=job.user_id,
        )

        session.commit()

        log_structured(
            logger=logger,
            level=logging.INFO,
            message="job_expired",
            payload={
                "job_id": str(job.job_id),
                "user_id": str(job.user_id),
                "deleted_artifact_count": deleted_count,
            },
        )
        return True

    def _delete_artifact(
        self,
        session: Session,
        storage_client: StorageClientProtocol,
        artifact: Artifact,
    ) -> bool:
        """Delete one artifact from storage and mark it deleted in DB.

        Returns True on success. Logs and returns False on storage error
        (e.g. object already absent in storage).
        """
        try:
            storage_client.delete_object(artifact.object_key)
        except Exception as exc:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="cleanup_storage_delete_failed",
                payload={
                    "artifact_id": str(artifact.artifact_id),
                    "object_key": artifact.object_key,
                    "error": str(exc)[:300],
                },
            )

        mark_artifact_deleted(session=session, artifact_id=artifact.artifact_id)
        return True
