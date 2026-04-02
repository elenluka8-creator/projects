"""Ingestion stage entry point.

Single public function: ingest(source, storage_client) -> NormalizedDocument

Responsibilities:
- Fetch the EPUB binary from object storage
- Delegate to EpubParser for content extraction
- Delegate to LanguageDetector for language detection
- Assemble and return a NormalizedDocument

Explicitly out of scope: DB writes, segmentation, translation, LLM calls.
"""
from __future__ import annotations

import logging
import uuid

from app.logging.structured import log_structured
from app.pipeline.ingestion.epub_parser import parse
from app.pipeline.ingestion.language_detector import LanguageDetector
from app.pipeline.ingestion.models import (
    DrmDetectedError,
    EpubParseError,
    NormalizedDocument,
    UploadedSourceArtifact,
)
from app.storage.client import StorageClientProtocol

logger = logging.getLogger(__name__)

# Module-level detector instance — seed applied once at import time.
_detector = LanguageDetector()


def ingest(
    source: UploadedSourceArtifact,
    storage_client: StorageClientProtocol,
) -> NormalizedDocument:
    """Run the ingestion stage for a single source artifact.

    Args:
        source:         Reference to the validated EPUB artifact in object storage.
        storage_client: Storage client for fetching the EPUB binary.

    Returns:
        NormalizedDocument — the authoritative document representation.

    Raises:
        DrmDetectedError:  EPUB is DRM-protected. Do not retry.
        EpubParseError:    EPUB is malformed or unreadable. Do not retry.
        LookupError:       Artifact not found in storage.
        RuntimeError:      Language detection failed after content extraction.
    """
    log_structured(
        logger=logger,
        level=logging.INFO,
        message="ingestion_started",
        payload={
            "artifact_id": str(source.artifact_id),
            "job_id": str(source.job_id),
            "user_id": str(source.user_id),
        },
    )

    epub_bytes = _fetch_epub(source, storage_client)

    # May raise DrmDetectedError or EpubParseError — propagate to caller.
    parsed = parse(epub_bytes)

    if not parsed.text:
        raise EpubParseError(
            f"EPUB artifact {source.artifact_id} produced no extractable text."
        )

    detected_language, confidence = _detector.detect(parsed.text)

    document = NormalizedDocument(
        document_id=uuid.uuid4(),
        source_type=source.source_type,
        title=parsed.title,
        author=parsed.author,
        text=parsed.text,
        detected_language=detected_language,
        detection_confidence=confidence,
        source_word_count=parsed.source_word_count,
        chapter_refs=parsed.chapter_refs,
        structural_refs=parsed.structural_refs,
        metadata=parsed.metadata,
    )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="ingestion_completed",
        payload={
            "artifact_id": str(source.artifact_id),
            "job_id": str(source.job_id),
            "document_id": str(document.document_id),
            "detected_language": document.detected_language,
            "detection_confidence": round(document.detection_confidence, 4),
            "source_word_count": document.source_word_count,
            "chapter_count": len(document.chapter_refs),
        },
    )

    return document


def _fetch_epub(
    source: UploadedSourceArtifact,
    storage_client: StorageClientProtocol,
) -> bytes:
    """Download the EPUB binary from object storage using the canonical key.

    Uses get_object_bytes() directly — presigned URLs are not used here because
    they can expire between artifact registration and job execution.
    """
    log_structured(
        logger=logger,
        level=logging.DEBUG,
        message="fetch_epub_start",
        payload={
            "artifact_id": str(source.artifact_id),
            "job_id": str(source.job_id),
            "storage_key": source.storage_key,
        },
    )
    try:
        raw = storage_client.get_object_bytes(source.storage_key)
        if raw is None:
            raise LookupError(
                f"Artifact not found in storage: key={source.storage_key!r}"
            )
    except LookupError:
        raise
    except Exception as exc:
        raise LookupError(
            f"Failed to fetch EPUB from storage: key={source.storage_key!r}: {exc}"
        ) from exc
    log_structured(
        logger=logger,
        level=logging.DEBUG,
        message="fetch_epub_done",
        payload={"storage_key": source.storage_key, "size_bytes": len(raw)},
    )
    return raw
