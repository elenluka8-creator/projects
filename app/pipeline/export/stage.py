"""Export stage entry point.

Single public function: export_document(formatted, source_epub_bytes, config) -> ExportedEpub

Responsibilities:
- Delegate EPUB reconstruction to epub_builder.build_epub()
- Compute SHA-256 fingerprint of the output bytes (POLICY-FINGERPRINT)
- Return ExportedEpub (pure data — no storage I/O, no DB writes)

Storage upload and DB record creation are handled by the orchestrator.
"""
from __future__ import annotations

import hashlib
import logging

from app.logging.structured import log_structured
from app.pipeline.export.epub_builder import build_epub
from app.pipeline.export.models import ExportConfig, ExportedEpub, ExportError
from app.pipeline.formatting.models import FormattedDocument

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"translate", "guided"})


def export_document(
    formatted: FormattedDocument,
    source_epub_bytes: bytes,
    config: ExportConfig,
) -> ExportedEpub:
    """Convert a FormattedDocument into a reconstructed EPUB binary.

    Args:
        formatted:         Output of the formatting stage.
        source_epub_bytes: Raw bytes of the original EPUB (fetched from storage).
        config:            Export configuration (mode, language, title, author).

    Returns:
        ExportedEpub with epub_bytes, sha256_fingerprint, and size_bytes.

    Raises:
        ExportError: If the EPUB cannot be built or inputs are invalid.
    """
    if config.mode not in _VALID_MODES:
        raise ExportError(
            f"Unsupported mode '{config.mode}'. Must be one of: {sorted(_VALID_MODES)}"
        )
    if not formatted.formatted_blocks:
        raise ExportError(
            f"FormattedDocument for job {config.job_id} has no formatted blocks."
        )
    if not source_epub_bytes:
        raise ExportError("source_epub_bytes must not be empty.")

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="export_started",
        payload={
            "job_id": str(config.job_id),
            "mode": config.mode,
            "target_language": config.target_language,
            "block_count": len(formatted.formatted_blocks),
        },
    )

    epub_bytes = build_epub(
        formatted=formatted,
        source_epub_bytes=source_epub_bytes,
        config=config,
    )

    fingerprint = hashlib.sha256(epub_bytes).hexdigest()
    size_bytes = len(epub_bytes)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="export_completed",
        payload={
            "job_id": str(config.job_id),
            "size_bytes": size_bytes,
            "sha256": fingerprint[:16] + "...",
        },
    )

    return ExportedEpub(
        epub_bytes=epub_bytes,
        sha256_fingerprint=fingerprint,
        size_bytes=size_bytes,
    )
