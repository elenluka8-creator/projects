"""Export stage data models.

Implements the pipeline contract from docs/PIPELINE_CONTRACTS.md §5 Export.
All types are frozen dataclasses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ExportConfig:
    """Job-level export configuration passed to the export stage.

    Derived from Job and Document records at orchestration time.
    """

    mode: str             # "translate" | "guided"
    target_language: str  # BCP-47 code (e.g. "en", "fr")
    source_title: str     # Original book title from ingestion
    source_author: str    # Original author from ingestion
    user_id: uuid.UUID
    job_id: uuid.UUID


@dataclass(frozen=True)
class ExportedEpub:
    """Result returned by the export stage.

    Contract fields per PIPELINE_CONTRACTS.md §5:
        epub_bytes         -- The complete reconstructed EPUB binary.
        sha256_fingerprint -- Hex-encoded SHA-256 hash of epub_bytes (POLICY-FINGERPRINT).
        size_bytes         -- Length of epub_bytes in bytes.
    """

    epub_bytes: bytes
    sha256_fingerprint: str
    size_bytes: int


class ExportError(Exception):
    """Base class for all export stage errors."""
