"""Lease management for worker job_run ownership.

Workers must hold an explicit, time-bounded lease on a job_run.
Lease expiry enables stuck-job recovery without blind re-processing.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.job import Job, JobRun
from app.logging.structured import log_structured

logger = logging.getLogger(__name__)


def acquire_lease(
    session: Session,
    job_run_id: uuid.UUID,
    worker_id: str,
    duration_seconds: int = 300,
) -> bool:
    """Acquire exclusive lease on a job_run.

    Returns True if lease was successfully acquired (run was in 'created' state).
    Returns False if the run is already leased or in a non-leasable state.
    """
    run = session.get(JobRun, job_run_id)
    if run is None:
        return False

    if run.status not in ("created",):
        return False

    now = datetime.now(timezone.utc)
    run.status = "leased"
    run.worker_id = worker_id
    run.lease_acquired_at = now
    run.lease_expires_at = now + timedelta(seconds=duration_seconds)
    run.heartbeat_at = now
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="lease_acquired",
        payload={
            "job_run_id": str(job_run_id),
            "worker_id": worker_id,
            "lease_expires_at": run.lease_expires_at.isoformat(),
        },
    )
    return True


def renew_lease(
    session: Session,
    job_run_id: uuid.UUID,
    worker_id: str,
    duration_seconds: int = 300,
) -> bool:
    """Renew an existing lease. Returns False if worker_id does not match."""
    run = session.get(JobRun, job_run_id)
    if run is None or run.worker_id != worker_id:
        return False

    now = datetime.now(timezone.utc)
    run.lease_expires_at = now + timedelta(seconds=duration_seconds)
    run.heartbeat_at = now
    session.flush()
    return True


def release_lease(
    session: Session,
    job_run_id: uuid.UUID,
    worker_id: str,
) -> None:
    """Release the lease. No-op if worker_id does not match."""
    run = session.get(JobRun, job_run_id)
    if run is None or run.worker_id != worker_id:
        return
    run.worker_id = None
    run.lease_expires_at = None
    session.flush()


def find_unqueued_created_runs(session: Session) -> List[JobRun]:
    """Return job_runs with status='created' whose parent job has status='queued'.

    Used at startup to re-enqueue runs that were in the Redis queue when the
    worker last stopped. The Redis queue does not persist across restarts, so
    these runs would otherwise be stuck indefinitely.
    """
    rows = session.execute(
        select(JobRun)
        .join(Job, JobRun.job_id == Job.job_id)
        .where(
            JobRun.status == "created",
            Job.status == "queued",
        )
    ).scalars().all()
    return list(rows)


def find_active_processing_runs(session: Session) -> List[JobRun]:
    """Return job_runs in 'leased' or 'processing' state with a non-expired lease.

    These are runs left mid-execution when the previous worker process was killed
    (e.g., by a redeploy). detect_expired_leases() does not cover them because
    their lease has not yet expired. On worker startup these should be reset to
    'created' and re-enqueued so the new worker can reprocess them.
    """
    now = datetime.now(timezone.utc)
    rows = session.execute(
        select(JobRun).where(
            JobRun.status.in_(["leased", "processing"]),
            or_(
                JobRun.lease_expires_at.is_(None),
                JobRun.lease_expires_at >= now,
            ),
        )
    ).scalars().all()
    return list(rows)


def detect_expired_leases(session: Session) -> List[JobRun]:
    """Return all job_runs with expired leases still in 'leased' or 'processing' status."""
    now = datetime.now(timezone.utc)
    rows = session.execute(
        select(JobRun).where(
            JobRun.status.in_(["leased", "processing"]),
            JobRun.lease_expires_at != None,  # noqa: E711
            JobRun.lease_expires_at < now,
        )
    ).scalars().all()
    return list(rows)
