"""Worker process entry point.

Run with:
    python3 -m app.worker.run

Behaviour:
- Initialises DB session, Redis broker, and S3 storage client once at startup.
- Loops forever calling WorkerOrchestrator.process_one().
- Sleeps 2 s between iterations when no work is available.
- Logs all unhandled exceptions and continues — the loop must not die on a
  single bad job; let the orchestrator's own error handling settle the run.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.job import Job, JobRun
from app.db.models.translation_batch import TranslationBatch
from app.db.models.user import User
from app.db.models.document import Document
from app.domain.services.credit_service import refund_credits
from app.logging.structured import log_structured
from app.notifications.notification_service import send_job_timeout_notification
from app.queue.broker import RedisQueueBroker
from app.storage.client import BotoStorageClient
from app.telemetry.timeline import emit_timeline_event
from app.retention.policy import stamp_retention_deadline
from app.worker.lease import (
    detect_expired_leases,
    find_active_processing_runs,
    find_timed_out_jobs,
    find_unqueued_created_runs,
)
from app.worker.orchestrator import WorkerOrchestrator

logger = logging.getLogger(__name__)

_IDLE_SLEEP_SECONDS = 2
_WATCHDOG_INTERVAL_SECONDS = 60
_JOB_TIMEOUT_SECONDS = int(os.environ.get("JOB_TIMEOUT_SECONDS", "7200"))


def _expire_timed_out_jobs(session: Session) -> list[tuple]:
    """Fail jobs that have been in an active state longer than the processing timeout.

    Returns a list of (job_id, user_id, ui_locale) tuples for post-commit notification dispatch.
    """
    timed_out = find_timed_out_jobs(session, timeout_seconds=_JOB_TIMEOUT_SECONDS)
    notifications: list[tuple] = []
    terminal_at = datetime.now(timezone.utc)

    for job in timed_out:
        failure_reason = "Processing timeout: job exceeded the maximum allowed processing time."
        job.status = "failed"
        job.failure_reason = failure_reason
        job.failure_class = "system"

        # Fail any active job_run for this job as well.
        active_run = session.execute(
            select(JobRun).where(
                JobRun.job_id == job.job_id,
                JobRun.status.in_(["created", "leased", "processing"]),
            )
        ).scalars().first()
        if active_run:
            active_run.status = "failed"
            active_run.completed_at = terminal_at
            active_run.failure_reason = failure_reason
            active_run.failure_class = "system"

        session.flush()
        stamp_retention_deadline(session, job, terminal_at=terminal_at)

        if job.credit_estimate and job.credit_estimate > 0:
            run_id = active_run.job_run_id if active_run else None
            refund_credits(
                session=session,
                user_id=job.user_id,
                job_id=job.job_id,
                job_run_id=run_id,
                amount=job.credit_estimate,
            )
            emit_timeline_event(
                session=session,
                job_id=job.job_id,
                event_type="credit_refunded",
                job_run_id=active_run.job_run_id if active_run else None,
                user_id=job.user_id,
            )

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_failed",
            job_run_id=active_run.job_run_id if active_run else None,
            user_id=job.user_id,
            error_class="system",
        )
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="job_timed_out",
            payload={
                "job_id": str(job.job_id),
                "user_id": str(job.user_id),
                "created_at": job.created_at.isoformat() if job.created_at else None,
            },
        )
        notifications.append((job.job_id, job.user_id, job.ui_locale))

    return notifications


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _run_watchdog(broker: RedisQueueBroker, shutdown_event: threading.Event) -> None:
    """Background thread: detect and re-queue orphaned job_runs every 60 seconds.
    Also enforces the per-job processing timeout."""
    while not shutdown_event.is_set():
        shutdown_event.wait(timeout=_WATCHDOG_INTERVAL_SECONDS)
        if shutdown_event.is_set():
            break
        session = SessionLocal()
        _orphan_ids: list[tuple] = []
        _timeout_notifications: list[tuple] = []
        try:
            orphans = detect_expired_leases(session)
            for run in orphans:
                run.status = "created"
                run.worker_id = None
                run.lease_expires_at = None
                job = session.get(Job, run.job_id)
                if job and job.status == "processing":
                    job.status = "queued"
                _orphan_ids.append((run.job_run_id, run.job_id))
            if orphans:
                session.commit()

            _timeout_notifications = _expire_timed_out_jobs(session)
            if _timeout_notifications:
                session.commit()
        except Exception:
            log_structured(
                logger=logger,
                level=logging.ERROR,
                message="watchdog_error",
                payload={},
                exc_info=True,
            )
        finally:
            session.close()

        for job_run_id, job_id in _orphan_ids:
            broker.enqueue(job_run_id)
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="orphaned_job_run_requeued",
                payload={
                    "job_run_id": str(job_run_id),
                    "job_id": str(job_id),
                },
            )

        base_url = os.environ.get("APP_BASE_URL", "https://app.unfolda.app")
        for job_id, user_id, ui_locale in _timeout_notifications:
            notification_session = SessionLocal()
            try:
                user = notification_session.get(User, user_id)
                doc = notification_session.execute(
                    select(Document).where(Document.job_id == job_id)
                ).scalars().first()
                if user:
                    book_title = (doc.title if doc and doc.title else None)
                    send_job_timeout_notification(
                        job_id=job_id,
                        user_id=user_id,
                        user_email=user.email,
                        display_name=user.display_name or user.email,
                        book_title=book_title,
                        ui_locale=ui_locale,
                        base_url=base_url,
                    )
            except Exception:
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="timeout_notification_setup_failed",
                    payload={"job_id": str(job_id)},
                )
            finally:
                notification_session.close()


def run() -> None:
    """Blocking worker loop. Exits only on SIGTERM/SIGINT."""
    _configure_logging()

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    broker = RedisQueueBroker(redis_url=redis_url)
    storage_client = BotoStorageClient()
    orchestrator = WorkerOrchestrator()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="worker_started",
        payload={"redis_url": redis_url},
    )

    shutdown_event = threading.Event()

    # Watchdog runs in a background thread so LLM-blocking process_one()
    # calls never prevent expired-lease detection.
    watchdog_thread = threading.Thread(
        target=_run_watchdog,
        args=(broker, shutdown_event),
        daemon=True,
        name="watchdog",
    )
    watchdog_thread.start()

    # Run an immediate watchdog pass on startup to recover any orphans.
    # Collect IDs while the session is open; enqueue only after session.close()
    # so a commit failure never leaves a run enqueued but not persisted.
    _orphan_ids: list[tuple] = []
    _unqueued_ids: list[tuple] = []
    session = SessionLocal()
    try:
        orphans = detect_expired_leases(session)
        for run in orphans:
            run.status = "created"
            run.worker_id = None
            run.lease_expires_at = None
            job = session.get(Job, run.job_id)
            if job and job.status == "processing":
                job.status = "queued"
            _orphan_ids.append((run.job_run_id, run.job_id))

        # Recover runs left in 'leased'/'processing' with an active (non-expired)
        # lease — these are orphaned by a previous worker process being killed
        # mid-job (e.g., by a Railway redeploy). detect_expired_leases() does not
        # cover them because the lease window has not yet elapsed.
        # Partial translation_batches for these runs are deleted so the run can
        # restart cleanly — re-inserting them would violate the unique constraint
        # on (job_run_id, batch_index). Consistency memory (job_consistency_snapshots)
        # is preserved since it is keyed by job_id, not job_run_id.
        active_stuck = find_active_processing_runs(session)
        for run in active_stuck:
            session.execute(
                delete(TranslationBatch).where(
                    TranslationBatch.job_run_id == run.job_run_id
                )
            )
            run.status = "created"
            run.worker_id = None
            run.lease_expires_at = None
            job = session.get(Job, run.job_id)
            if job and job.status in ("processing", "queued"):
                job.status = "queued"
            _orphan_ids.append((run.job_run_id, run.job_id))

        if orphans or active_stuck:
            session.commit()

        # Re-enqueue created runs that were not in the Redis queue before the restart.
        try:
            unqueued = find_unqueued_created_runs(session)
            for run in unqueued:
                _unqueued_ids.append((run.job_run_id, run.job_id))
        except Exception:
            log_structured(
                logger=logger,
                level=logging.ERROR,
                message="startup_recovery_error",
                payload={},
                exc_info=True,
            )
    except Exception:
        log_structured(logger=logger, level=logging.ERROR, message="watchdog_error", payload={}, exc_info=True)
    finally:
        session.close()

    for job_run_id, job_id in _orphan_ids:
        broker.enqueue(job_run_id)
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="orphaned_job_run_requeued",
            payload={"job_run_id": str(job_run_id), "job_id": str(job_id)},
        )

    for job_run_id, job_id in _unqueued_ids:
        broker.enqueue(job_run_id)
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="created_job_run_recovered",
            payload={"job_run_id": str(job_run_id), "job_id": str(job_id)},
        )

    def _handle_signal(signum, frame):  # noqa: ANN001
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="worker_shutdown_requested",
            payload={"signal": signum},
        )
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    while not shutdown_event.is_set():
        session = SessionLocal()
        try:
            result = orchestrator.process_one(
                session=session,
                broker=broker,
                storage_client=storage_client,
            )
            if result is False:
                time.sleep(_IDLE_SLEEP_SECONDS)
        except Exception:
            log_structured(
                logger=logger,
                level=logging.ERROR,
                message="worker_loop_error",
                payload={},
                exc_info=True,
            )
            time.sleep(_IDLE_SLEEP_SECONDS)
        finally:
            session.close()

    shutdown_event.set()
    log_structured(
        logger=logger,
        level=logging.INFO,
        message="worker_stopped",
        payload={},
    )


if __name__ == "__main__":
    run()
