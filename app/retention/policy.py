"""Retention policy for job content lifecycle.

RETENTION_WINDOW_DAYS — number of days after terminal state before content
artifacts are eligible for deletion. Configurable via environment variable.

Default: 30 days (balances privacy requirements with download availability).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.job import Job
from app.logging.structured import log_structured

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_WINDOW_DAYS = 30


def get_retention_window_days() -> int:
    """Return the configured retention window in days."""
    raw = os.getenv("RETENTION_WINDOW_DAYS", str(_DEFAULT_RETENTION_WINDOW_DAYS))
    try:
        days = int(raw)
        if days < 1:
            raise ValueError("must be positive")
        return days
    except ValueError:
        logger.warning(
            "Invalid RETENTION_WINDOW_DAYS=%r; using default %d",
            raw,
            _DEFAULT_RETENTION_WINDOW_DAYS,
        )
        return _DEFAULT_RETENTION_WINDOW_DAYS


def stamp_retention_deadline(
    session: Session,
    job: Job,
    terminal_at: Optional[datetime] = None,
) -> None:
    """Set the retention deadline on a terminal job if not already set.

    Called by the worker orchestrator when a job reaches a terminal state
    (completed, failed, or cancelled). The deadline is:
        terminal_at + RETENTION_WINDOW_DAYS

    Idempotent: if retention_deadline is already set, this is a no-op.

    Args:
        session: SQLAlchemy session (caller responsible for commit).
        job: The Job record to stamp.
        terminal_at: Time of terminal transition (defaults to utcnow).
    """
    if job.retention_deadline is not None:
        return

    base = terminal_at or datetime.now(timezone.utc)
    window = get_retention_window_days()
    deadline = base + timedelta(days=window)

    job.retention_deadline = deadline
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="retention_deadline_set",
        payload={
            "job_id": str(job.job_id),
            "user_id": str(job.user_id),
            "terminal_at": base.isoformat(),
            "retention_deadline": deadline.isoformat(),
            "window_days": window,
        },
    )
