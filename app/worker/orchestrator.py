"""Worker orchestrator — the core job execution loop.

process_one() dequeues one job_run, acquires a lease, executes the pipeline,
settles credits, and transitions to a terminal state.

Pipeline execution model for MVP:
  - INGEST stage: fully implemented (app.pipeline.ingestion)
  - SEGMENT stage: fully implemented (app.pipeline.segmentation)
  - TRANSLATE stage: fully implemented (app.pipeline.translation)
  - FORMAT stage: fully implemented (app.pipeline.formatting)
  - EXPORT stage: fully implemented (app.pipeline.export)

Cancellation is checked at each stage boundary (honor cancel_requested).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.job import Job, JobRun
from app.db.models.user import User
from app.domain.services.credit_service import consume_credits, refund_credits
from app.domain.services.progress_model import (
    compute_eta_seconds,
    cumulative_percent_after_stage,
    translate_progress_percent,
)
from app.logging.structured import log_structured
from app.pipeline.ingestion.models import DrmDetectedError, EpubParseError, NormalizedDocument
from app.pipeline.ingestion.models import UploadedSourceArtifact
from app.pipeline.ingestion.stage import ingest
from app.pipeline.segmentation.models import SegmentCollection
from app.pipeline.segmentation.stage import segment, SegmentationError
from app.pipeline.translation.consistency import ConsistencyMemory
from app.domain.services.consistency_repository import ConsistencyRepository
from app.pipeline.translation.preamble import PreambleResult
from app.pipeline.translation.models import (
    ContentDeterministicError,
    ProviderBillingError,
    ProviderTransientError,
    TranslationConfig,
    TranslatedSegment,
    TranslatedSegmentCollection,
)
from app.pipeline.translation.provider import AnthropicProvider
from app.config.policy import get_tier_model
from app.pipeline.translation.stage import translate as run_translation
from app.pipeline.formatting.models import FormattedDocument
from app.pipeline.formatting.stage import format_document
from app.pipeline.export.models import ExportConfig
from app.pipeline.export.stage import export_document
from app.db.models.artifact import Artifact
from app.cost.ledger import record_batch_cost
from app.db.models.translation_batch import TranslationBatch
from app.queue.broker import QueueBrokerProtocol
from app.storage.client import StorageClientProtocol
from app.telemetry.timeline import emit_timeline_event
from app.retention.policy import stamp_retention_deadline
from app.notifications.notification_service import send_job_completion_notification
from app.worker.lease import acquire_lease, release_lease, renew_lease

logger = logging.getLogger(__name__)


class _UUIDEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def _serialize_translated_collection(translated: TranslatedSegmentCollection) -> bytes:
    """Serialize a TranslatedSegmentCollection to JSON bytes for S3 storage."""
    return json.dumps(dataclasses.asdict(translated), ensure_ascii=False, cls=_UUIDEncoder).encode("utf-8")


def _deserialize_translated_collection(data: bytes) -> TranslatedSegmentCollection:
    """Reconstruct a TranslatedSegmentCollection from JSON bytes loaded from S3."""
    d = json.loads(data)
    segments = [TranslatedSegment(**s) for s in d["translated_segments"]]
    return TranslatedSegmentCollection(
        document_id=uuid.UUID(d["document_id"]),
        mode=d["mode"],
        translated_segments=segments,
    )


_PIPELINE_STAGES = ("ingest", "segment", "translate", "format", "export")
_LEASE_DURATION_SECONDS = int(os.environ.get("WORKER_LEASE_DURATION_SECONDS", "28800"))
def _normalize_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


_WORKER_ID_PREFIX = "worker"


class WorkerOrchestrator:
    """Stateless worker that processes one job_run per call."""

    def __init__(self, worker_id: Optional[str] = None) -> None:
        self._worker_id = worker_id or f"{_WORKER_ID_PREFIX}-{uuid.uuid4().hex[:8]}"

    def _persist_job_progress(
        self,
        session: Session,
        job: Job,
        *,
        stage: str,
        percent: int,
    ) -> None:
        """Persist durable progress + ETA on Job (DEC-010)."""
        session.refresh(job)
        now = datetime.now(timezone.utc)
        if job.processing_started_at is None:
            job.processing_started_at = now
        start = _normalize_aware(job.processing_started_at)
        job.processing_started_at = start
        job.pipeline_stage = stage
        job.progress_percent = min(100, max(0, percent))
        elapsed = (now - start).total_seconds()
        job.eta_seconds_remaining = compute_eta_seconds(elapsed, job.progress_percent)
        session.flush()

    def process_one(
        self,
        session: Session,
        broker: QueueBrokerProtocol,
        storage_client: StorageClientProtocol,
    ) -> Optional[bool]:
        """Dequeue and process one job_run.

        Returns:
            True  — processing completed (success or handled failure)
            False — no work available
            None  — lease acquisition failed (someone else grabbed it)
        """
        job_run_id = broker.dequeue(timeout_seconds=0)
        if job_run_id is None:
            return False

        acquired = acquire_lease(
            session=session,
            job_run_id=job_run_id,
            worker_id=self._worker_id,
            duration_seconds=_LEASE_DURATION_SECONDS,
        )
        if not acquired:
            # Re-enqueue only if the run is still in a processable state.
            # Avoids infinite loops for cancelled/completed runs.
            run_check = session.get(JobRun, job_run_id)
            if run_check is not None and run_check.status == "created":
                broker.enqueue(job_run_id)
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="lease_acquisition_failed_requeued",
                    payload={"job_run_id": str(job_run_id), "worker_id": self._worker_id},
                )
            else:
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="lease_acquisition_failed",
                    payload={"job_run_id": str(job_run_id), "worker_id": self._worker_id},
                )
            return None

        run = session.get(JobRun, job_run_id)
        if run is None:
            return None

        job = session.get(Job, run.job_id)
        if job is None:
            return None

        session.commit()

        try:
            self._execute_pipeline(session, job, run, storage_client)
        except Exception as exc:
            self._handle_failure(session, job, run, exc)
            session.commit()
            return True
        finally:
            release_lease(session=session, job_run_id=job_run_id, worker_id=self._worker_id)
            session.commit()

        return True

    def _execute_pipeline(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        storage_client: StorageClientProtocol,
    ) -> None:
        run.status = "processing"
        job.status = "processing"
        session.flush()

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_run_leased",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
        )
        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_processing_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
        )
        session.commit()

        if self._check_cancellation(session, job, run):
            return

        # --- INGEST stage (real implementation) ---
        # doc may be None when source_artifact_id is absent (e.g. test jobs)
        doc, normalized_doc = self._run_ingest(session, job, run, storage_client)

        if self._check_cancellation(session, job, run):
            return

        # --- SEGMENT stage ---
        segment_collection = self._run_segment(session, job, run, normalized_doc)
        if self._check_cancellation(session, job, run):
            return

        # --- TRANSLATE stage ---
        translated_collection = self._run_translate(session, job, run, segment_collection, storage_client)
        if self._check_cancellation(session, job, run):
            return

        # --- FORMAT stage ---
        formatted_document = self._run_format(session, job, run, translated_collection)
        if self._check_cancellation(session, job, run):
            return

        # --- EXPORT stage ---
        self._run_export(session, job, run, formatted_document, storage_client)
        if self._check_cancellation(session, job, run):
            return

        # Terminal success
        self._complete_job(session, job, run)

    def _run_ingest(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        storage_client: StorageClientProtocol,
    ) -> Tuple[Optional[Document], Optional[NormalizedDocument]]:
        if job.source_artifact_id is None:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="ingest_skipped_no_artifact",
                payload={"job_id": str(job.job_id)},
            )
            self._persist_job_progress(
                session,
                job,
                stage="ingest",
                percent=cumulative_percent_after_stage("ingest"),
            )
            return None, None

        source_artifact = session.get(Artifact, job.source_artifact_id)
        if source_artifact is None:
            raise LookupError(
                f"Source artifact {job.source_artifact_id} not found in DB "
                f"(job_id={job.job_id})."
            )
        log_structured(
            logger=logger,
            level=logging.DEBUG,
            message="ingest_source_artifact",
            payload={
                "artifact_id": str(job.source_artifact_id),
                "object_key": source_artifact.object_key,
            },
        )
        source = UploadedSourceArtifact(
            artifact_id=job.source_artifact_id,
            user_id=job.user_id,
            job_id=job.job_id,
            storage_key=source_artifact.object_key,
        )

        try:
            normalized = ingest(source=source, storage_client=storage_client)
        except (DrmDetectedError, EpubParseError) as exc:
            raise exc

        # Guard against duplicate Document on retry: the documents table has a
        # unique constraint on job_id. If a Document already exists from a
        # previous attempt, reuse it rather than inserting a duplicate.
        existing_doc = session.query(Document).filter_by(job_id=job.job_id).first()
        if existing_doc is None:
            doc = Document(
                job_id=job.job_id,
                user_id=job.user_id,
                source_type=normalized.source_type,
                title=normalized.title,
                author=normalized.author,
                detected_language=normalized.detected_language,
                detection_confidence=normalized.detection_confidence,
                source_word_count=normalized.source_word_count,
                chapter_count=len(normalized.chapter_refs),
            )
            session.add(doc)
            session.flush()
            session.commit()
        else:
            doc = existing_doc
        self._persist_job_progress(
            session,
            job,
            stage="ingest",
            percent=cumulative_percent_after_stage("ingest"),
        )
        return doc, normalized

    def _run_segment(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        normalized_doc: Optional[NormalizedDocument],
    ) -> Optional[SegmentCollection]:
        """Run the segmentation stage using the real implementation.

        Updates Document.estimated_batch_count and estimated_token_count from
        batch-planning output. Falls back gracefully when normalized_doc is None
        (e.g. jobs submitted without a source artifact in tests).
        """
        if normalized_doc is None:
            self._run_stub_stage(session, job, run, stage="segment")
            self._persist_job_progress(
                session,
                job,
                stage="segment",
                percent=cumulative_percent_after_stage("segment"),
            )
            return None

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="segment",
        )

        try:
            collection = segment(document=normalized_doc, mode=job.mode or "translate")
        except SegmentationError as exc:
            raise exc

        # Persist batch-planning metadata into the Document record.
        doc = session.query(Document).filter_by(job_id=job.job_id).first()
        if doc is not None:
            doc.estimated_batch_count = collection.batch_planning.estimated_batch_count
            total_tokens = sum(s.token_estimate for s in collection.segments)
            doc.estimated_token_count = total_tokens
            session.flush()

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="segment",
        )
        session.commit()
        return collection


    def _run_translate(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        segment_collection,
        storage_client: StorageClientProtocol,
    ):
        """Run the translation stage using the real AnthropicProvider implementation.

        Iterates over translation batches, creates TranslationBatch DB records,
        emits timeline events, and records cost ledger entries per batch (DEC-006,
        DEC-008). Falls back to stub when segment_collection is None.

        On resume, skips all translation work if all batches are already completed
        in the DB and the serialized artifact can be loaded from S3.

        Returns:
            TranslatedSegmentCollection or None when skipped.
        """
        if segment_collection is None:
            self._run_stub_stage(session, job, run, stage="translate")
            self._persist_job_progress(
                session,
                job,
                stage="translate",
                percent=cumulative_percent_after_stage("translate"),
            )
            return None

        # --- Resumability: skip if all batches already completed ---
        completed_batch_indices: set[int] = {
            row[0]
            for row in session.execute(
                select(TranslationBatch.batch_index).where(
                    TranslationBatch.job_run_id == run.job_run_id,
                    TranslationBatch.status == "completed",
                )
            ).all()
        }
        # Use actual DB count, not planning estimates — estimates may differ from actual batch count
        total_batches_in_db = session.execute(
            select(func.count(TranslationBatch.batch_id)).where(
                TranslationBatch.job_run_id == run.job_run_id
            )
        ).scalar_one()

        if total_batches_in_db > 0 and len(completed_batch_indices) >= total_batches_in_db:
            artifact_key = (
                f"users/{job.user_id}/jobs/{job.job_id}"
                f"/translation_artifacts/{run.job_run_id}/translated_collection.json"
            )
            loaded_collection = None
            try:
                raw = storage_client.get_object_bytes(artifact_key)
                loaded_collection = _deserialize_translated_collection(raw)
            except Exception:
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="translation_artifact_missing_rerunning",
                    payload={
                        "job_run_id": str(run.job_run_id),
                        "artifact_key": artifact_key,
                    },
                )
                # Fall through to full re-run

            if loaded_collection is not None:
                log_structured(
                    logger=logger,
                    level=logging.INFO,
                    message="translation_skipped_all_complete",
                    payload={"job_run_id": str(run.job_run_id), "job_id": str(job.job_id)},
                )
                self._persist_job_progress(
                    session,
                    job,
                    stage="translate",
                    percent=cumulative_percent_after_stage("translate"),
                )
                return loaded_collection

        quality_tier = job.quality_tier or "standard"
        tier_model = get_tier_model(quality_tier)
        provider = AnthropicProvider(model=tier_model)

        # Stamp run metadata (POLICY-VERSION)
        run.prompt_version = f"translate-batch-v1|guided-batch-v1"
        run.provider_config_version = f"anthropic/{provider.model}"
        session.flush()

        config = TranslationConfig(
            mode=job.mode or "translate",
            target_language=job.target_language or "en",
            source_language=job.source_language_override or "auto",
            translation_style=job.translation_style or "natural",
            user_level=job.user_level or "B1",
            explanation_depth=job.explanation_depth or "standard",
            quality_tier=quality_tier,
        )

        # Restore persisted consistency state (survives worker restarts).
        memory = ConsistencyRepository.load(session, job_id=job.job_id)
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="consistency_memory_loaded",
            payload={
                "job_id": str(job.job_id),
                "terms": len(memory.terminology_map),
                "entities": len(memory.named_entity_registry),
            },
        )

        # Renew lease before the preamble LLM call which can take 1-3 minutes
        # on large books. Without renewal the 300-second lease could expire
        # before the first batch_complete, causing the watchdog to re-queue.
        renew_lease(
            session=session,
            job_run_id=run.job_run_id,
            worker_id=self._worker_id,
            duration_seconds=_LEASE_DURATION_SECONDS,
        )
        session.commit()

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="translate",
        )
        session.commit()

        n_hints = len(segment_collection.batch_planning.batch_boundary_hints)
        est = int(segment_collection.batch_planning.estimated_batch_count or 0)
        total_batches = max(1, n_hints, est)

        def _on_preamble_complete(preamble_result: PreambleResult) -> None:
            """Record preamble cost, persist initial memory, emit timeline event."""
            if preamble_result.skipped:
                log_structured(
                    logger=logger,
                    level=logging.INFO,
                    message="preamble_skipped",
                    payload={"job_id": str(job.job_id), "reason": preamble_result.skip_reason},
                )
                return

            record_batch_cost(
                session=session,
                job_id=job.job_id,
                tokens_in=preamble_result.tokens_in,
                tokens_out=preamble_result.tokens_out,
                job_run_id=run.job_run_id,
                batch_index=-1,  # sentinel: preamble pass
                provider="anthropic",
            )
            ConsistencyRepository.save(
                session=session,
                job_id=job.job_id,
                batch_index=-1,
                memory=memory,
            )
            emit_timeline_event(
                session=session,
                job_id=job.job_id,
                event_type="preamble_analyzed",
                job_run_id=run.job_run_id,
                user_id=job.user_id,
                payload={
                    "characters": len(memory.named_entity_registry),
                    "terms": len(memory.terminology_map),
                    "tokens_in": preamble_result.tokens_in,
                    "tokens_out": preamble_result.tokens_out,
                },
            )
            session.commit()

        def _on_batch_complete(batch_index: int, result) -> None:
            """Per-batch DB checkpoint, cost recording, and consistency persist."""
            # Renew lease so a long translation never loses it mid-book.
            renew_lease(
                session=session,
                job_run_id=run.job_run_id,
                worker_id=self._worker_id,
                duration_seconds=_LEASE_DURATION_SECONDS,
            )
            tb = TranslationBatch(
                job_run_id=run.job_run_id,
                job_id=job.job_id,
                batch_index=batch_index,
                chapter_ref=None,
                status="completed",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
            )
            session.add(tb)
            session.flush()

            record_batch_cost(
                session=session,
                job_id=job.job_id,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cache_read_tokens=result.cache_read_tokens,
                job_run_id=run.job_run_id,
                batch_index=batch_index,
                provider="anthropic",
            )
            # Persist consistency memory so a restart can resume from here.
            ConsistencyRepository.save(
                session=session,
                job_id=job.job_id,
                batch_index=batch_index,
                memory=memory,
            )
            self._persist_job_progress(
                session,
                job,
                stage="translate",
                percent=translate_progress_percent(batch_index, total_batches),
            )
            session.commit()

        translated = run_translation(
            collection=segment_collection,
            config=config,
            provider=provider,
            consistency_memory=memory,
            on_batch_complete=_on_batch_complete,
            on_preamble_complete=_on_preamble_complete,
        )

        # Persist the translated collection to S3 for resumability on future restarts.
        _translation_artifact_key = (
            f"users/{job.user_id}/jobs/{job.job_id}"
            f"/translation_artifacts/{run.job_run_id}/translated_collection.json"
        )
        try:
            _raw = _serialize_translated_collection(translated)
            storage_client.put_object_bytes(
                _translation_artifact_key, _raw, content_type="application/json"
            )
            _artifact = Artifact(
                artifact_id=uuid.uuid4(),
                user_id=job.user_id,
                job_id=job.job_id,
                artifact_type="translation_collection",
                object_key=_translation_artifact_key,
                storage_status="active",
            )
            session.add(_artifact)
            session.flush()
        except Exception:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="translation_artifact_persist_failed",
                payload={"job_run_id": str(run.job_run_id)},
            )

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="translate",
            payload={
                "segment_count": len(translated.translated_segments),
            },
        )
        session.commit()
        self._persist_job_progress(
            session,
            job,
            stage="translate",
            percent=cumulative_percent_after_stage("translate"),
        )
        return translated


    def _run_format(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        translated_collection,
    ):
        """Run the formatting stage using the real implementation.

        Purely deterministic — no LLM calls, no cost ledger entries.
        Emits batch_started/batch_completed timeline events and returns a
        FormattedDocument. Falls back to stub when translated_collection is None.

        Returns:
            FormattedDocument or None when skipped.
        """
        if translated_collection is None:
            self._run_stub_stage(session, job, run, stage="format")
            self._persist_job_progress(
                session,
                job,
                stage="format",
                percent=cumulative_percent_after_stage("format"),
            )
            return None

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="format",
        )
        session.flush()

        formatted = format_document(translated_collection)

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="format",
            payload={"block_count": len(formatted.formatted_blocks)},
        )
        session.commit()
        self._persist_job_progress(
            session,
            job,
            stage="format",
            percent=cumulative_percent_after_stage("format"),
        )
        return formatted


    def _run_export(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        formatted_document,
        storage_client: StorageClientProtocol,
    ):
        """Run the export stage.

        Fetches the source EPUB bytes from storage, builds the output EPUB,
        uploads it, creates an Artifact record, and sets job.output_artifact_id.
        Falls back to stub when formatted_document or source_artifact_id is None.
        """
        if formatted_document is None or job.source_artifact_id is None:
            self._run_stub_stage(session, job, run, stage="export")
            self._persist_job_progress(
                session,
                job,
                stage="export",
                percent=cumulative_percent_after_stage("export"),
            )
            return None


        source_artifact = session.get(Artifact, job.source_artifact_id)
        if source_artifact is None:
            raise LookupError(
                f"Source artifact {job.source_artifact_id} not found in DB "
                f"(job_id={job.job_id})."
            )
        log_structured(
            logger=logger,
            level=logging.DEBUG,
            message="export_source_artifact",
            payload={
                "artifact_id": str(job.source_artifact_id),
                "object_key": source_artifact.object_key,
            },
        )
        try:
            source_epub_bytes = storage_client.get_object_bytes(source_artifact.object_key)
        except Exception as exc:
            raise LookupError(
                f"Cannot fetch source EPUB for export: "
                f"key={source_artifact.object_key!r}: {exc}"
            ) from exc


        doc = session.query(Document).filter_by(job_id=job.job_id).first()
        source_title = (doc.title if doc and doc.title else "Unknown Title")
        source_author = (doc.author if doc and doc.author else "Unknown Author")

        config = ExportConfig(
            mode=job.mode or "translate",
            target_language=job.target_language or "en",
            source_title=source_title,
            source_author=source_author,
            user_id=job.user_id,
            job_id=job.job_id,
        )

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="export",
        )
        session.flush()

        exported = export_document(
            formatted=formatted_document,
            source_epub_bytes=source_epub_bytes,
            config=config,
        )

        artifact_id = uuid.uuid4()
        object_key = (
            f"users/{job.user_id}/jobs/{job.job_id}"
            f"/output_epub/{artifact_id}"
        )
        storage_client.put_object_bytes(object_key, exported.epub_bytes)

        artifact = Artifact(
            artifact_id=artifact_id,
            user_id=job.user_id,
            job_id=job.job_id,
            artifact_type="output_epub",
            object_key=object_key,
            size_bytes=exported.size_bytes,
            content_sha256=exported.sha256_fingerprint,
            mime_type="application/epub+zip",
        )
        session.add(artifact)
        job.output_artifact_id = artifact_id
        session.flush()

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage="export",
            payload={"size_bytes": exported.size_bytes},
        )
        session.commit()
        self._persist_job_progress(
            session,
            job,
            stage="export",
            percent=cumulative_percent_after_stage("export"),
        )
        return exported

    def _run_stub_stage(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        stage: str,
    ) -> None:
        """Stub for unimplemented pipeline stages. Emits timeline events."""
        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_started",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage=stage,
        )
        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="batch_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            stage=stage,
        )
        session.commit()

    def _check_cancellation(
        self,
        session: Session,
        job: Job,
        run: JobRun,
    ) -> bool:
        session.refresh(job)
        if not job.cancel_requested:
            return False

        terminal_at = datetime.now(timezone.utc)
        run.status = "cancelled"
        run.completed_at = terminal_at
        job.status = "cancelled"
        session.flush()
        stamp_retention_deadline(session, job, terminal_at=terminal_at)

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_cancelled",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
        )

        if job.credit_estimate and job.credit_estimate > 0:
            refund_credits(
                session=session,
                user_id=job.user_id,
                job_id=job.job_id,
                job_run_id=run.job_run_id,
                amount=job.credit_estimate,
            )
            emit_timeline_event(
                session=session,
                job_id=job.job_id,
                event_type="credit_refunded",
                job_run_id=run.job_run_id,
                user_id=job.user_id,
            )

        session.commit()
        return True

    def _complete_job(self, session: Session, job: Job, run: JobRun) -> None:
        terminal_at = datetime.now(timezone.utc)
        run.status = "completed"
        run.completed_at = terminal_at
        job.status = "completed"
        job.progress_percent = 100
        job.pipeline_stage = "export"
        job.eta_seconds_remaining = None
        session.flush()
        stamp_retention_deadline(session, job, terminal_at=terminal_at)

        if job.credit_estimate and job.credit_estimate > 0:
            consume_credits(
                session=session,
                user_id=job.user_id,
                job_id=job.job_id,
                job_run_id=run.job_run_id,
                amount=job.credit_estimate,
            )
            emit_timeline_event(
                session=session,
                job_id=job.job_id,
                event_type="credit_consumed",
                job_run_id=run.job_run_id,
                user_id=job.user_id,
            )

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_completed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
        )
        session.commit()

        try:
            user = session.get(User, job.user_id)
            if user is not None:
                doc = session.query(Document).filter_by(job_id=job.job_id).first()
                book_title = doc.title if doc and doc.title else "your book"
                base_url = os.environ.get("APP_BASE_URL", "https://app.unfolda.app")
                send_job_completion_notification(
                    job_id=job.job_id,
                    user_id=job.user_id,
                    user_email=user.email,
                    display_name=user.display_name or user.email,
                    book_title=book_title,
                    ui_locale=job.ui_locale,
                    base_url=base_url,
                )
        except Exception as _notify_exc:
            log_structured(
                logger,
                logging.WARNING,
                "notification_setup_failed",
                {"job_id": str(job.job_id), "error": type(_notify_exc).__name__},
            )

    def _handle_failure(
        self,
        session: Session,
        job: Job,
        run: JobRun,
        exc: Exception,
    ) -> None:
        failure_class = _classify_failure(exc)
        reason = str(exc)[:500]

        terminal_at = datetime.now(timezone.utc)
        run.status = "failed"
        run.completed_at = terminal_at
        run.failure_reason = reason
        run.failure_class = failure_class
        job.status = "failed"
        job.failure_reason = reason
        job.failure_class = failure_class
        session.flush()
        stamp_retention_deadline(session, job, terminal_at=terminal_at)

        if job.credit_estimate and job.credit_estimate > 0:
            refund_credits(
                session=session,
                user_id=job.user_id,
                job_id=job.job_id,
                job_run_id=run.job_run_id,
                amount=job.credit_estimate,
            )
            emit_timeline_event(
                session=session,
                job_id=job.job_id,
                event_type="credit_refunded",
                job_run_id=run.job_run_id,
                user_id=job.user_id,
            )

        emit_timeline_event(
            session=session,
            job_id=job.job_id,
            event_type="job_failed",
            job_run_id=run.job_run_id,
            user_id=job.user_id,
            error_class=failure_class,
        )

        log_structured(
            logger=logger,
            level=logging.ERROR,
            message="job_failed",
            payload={
                "job_id": str(job.job_id),
                "job_run_id": str(run.job_run_id),
                "failure_class": failure_class,
            },
        )


def _classify_failure(exc: Exception) -> str:
    if isinstance(exc, (DrmDetectedError, EpubParseError)):
        return "content-deterministic"
    if isinstance(exc, ContentDeterministicError):
        return "content-deterministic"
    if isinstance(exc, ProviderTransientError):
        return "provider-transient"
    if isinstance(exc, ProviderBillingError):
        return "system"
    if isinstance(exc, LookupError):
        return "system"
    return "system"
