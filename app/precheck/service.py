"""Pre-submission analysis service (FEAT-PRECHECK).

Downloads a validated source EPUB from storage, extracts advisory metadata
for the CONFIG screen and credit estimation. Results are advisory only —
authoritative metadata is produced by the ingestion pipeline stage (DEC-011).

Caller contract:
  - Raises LookupError if artifact not found or deleted.
  - Raises PermissionError if the user does not own the artifact.
  - Raises ValueError if the artifact has not been validated or is not a source_epub.
  - Never raises on EPUB parse failures or language detection failures —
    those are recorded as status=failed with an error_code.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.artifact import Artifact
from app.db.models.precheck import PreCheckResult
from app.logging.structured import log_structured
from app.storage.client import StorageClientProtocol

logger = logging.getLogger(__name__)


def run_precheck(
    session: Session,
    client: StorageClientProtocol,
    artifact_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PreCheckResult:
    """Run pre-submission analysis for a validated source EPUB.

    Idempotent: if a completed or failed record exists for the artifact,
    it is returned without re-running the analysis.

    Returns the PreCheckResult record. On internal errors (parse failure,
    storage unavailable), returns a record with status='failed'.
    """
    # Guard: artifact must exist, be owned, be validated source_epub
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.storage_status == "deleted":
        raise LookupError(f"Artifact {artifact_id} not found or has been deleted.")
    if artifact.user_id != user_id:
        raise PermissionError(
            f"Artifact {artifact_id} does not belong to the requesting user."
        )
    if artifact.artifact_type != "source_epub":
        raise ValueError(
            f"Expected artifact_type 'source_epub', got '{artifact.artifact_type}'."
        )
    if artifact.validated_at is None:
        raise ValueError(
            "Artifact has not been validated. Run POST /upload/confirm first."
        )

    # Idempotent: return existing terminal result
    existing: Optional[PreCheckResult] = session.execute(
        select(PreCheckResult).where(PreCheckResult.artifact_id == artifact_id)
    ).scalar_one_or_none()
    if existing is not None and existing.status in ("completed", "failed"):
        return existing

    # Create pending record (or reuse existing pending one)
    if existing is None:
        record = PreCheckResult(
            precheck_id=uuid.uuid4(),
            artifact_id=artifact_id,
            user_id=user_id,
            status="pending",
        )
        session.add(record)
        session.flush()
    else:
        record = existing

    start_time = time.monotonic()

    # Download EPUB bytes
    try:
        data = client.get_object_bytes(artifact.object_key)
    except Exception as exc:
        return _mark_failed(session, record, "storage_unavailable", start_time, exc)

    # Parse EPUB (reuse ingestion parser — read-only, no pipeline artifacts produced)
    try:
        from app.pipeline.ingestion import epub_parser
        from app.pipeline.ingestion.models import EpubParseError, DrmDetectedError

        parsed = epub_parser.parse(data)
    except Exception as exc:
        error_code = (
            "drm_detected"
            if "DrmDetectedError" in type(exc).__name__
            else "epub_parse_failed"
        )
        return _mark_failed(session, record, error_code, start_time, exc)

    # Detect language (fallback to unknown on any failure — not a blocking error)
    lang_code = "unknown"
    confidence = 0.0
    if parsed.text and parsed.text.strip():
        try:
            from app.pipeline.ingestion.language_detector import LanguageDetector

            lang_code, confidence = LanguageDetector().detect(parsed.text)
        except Exception as exc:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="precheck_language_detection_failed",
                payload={
                    "artifact_id": str(artifact_id),
                    "user_id": str(user_id),
                    "error": str(exc),
                },
            )

    # Structural signals
    has_images = any(
        r.ref_type == "image" for r in parsed.structural_refs
    )

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    record.status = "completed"
    record.detected_language = lang_code
    record.language_confidence = round(confidence, 4)
    record.word_count = parsed.source_word_count
    record.chapter_count = len(parsed.chapter_refs)
    record.has_images = has_images
    record.completed_at = datetime.now(timezone.utc)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="precheck_completed",
        payload={
            "artifact_id": str(artifact_id),
            "user_id": str(user_id),
            "detected_language": lang_code,
            "language_confidence": round(confidence, 4),
            "word_count": parsed.source_word_count,
            "chapter_count": len(parsed.chapter_refs),
            "has_images": has_images,
            "elapsed_ms": elapsed_ms,
        },
    )

    return record


def _mark_failed(
    session: Session,
    record: PreCheckResult,
    error_code: str,
    start_time: float,
    exc: Exception,
) -> PreCheckResult:
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    record.status = "failed"
    record.error_code = error_code
    record.completed_at = datetime.now(timezone.utc)
    session.flush()
    log_structured(
        logger=logger,
        level=logging.WARNING,
        message="precheck_failed",
        payload={
            "artifact_id": str(record.artifact_id),
            "user_id": str(record.user_id),
            "error_code": error_code,
            "elapsed_ms": elapsed_ms,
        },
    )
    return record
