"""Ingestion stage data models.

Implements the pipeline contract from docs/PIPELINE_CONTRACTS.md §1 Ingestion.
All types are frozen dataclasses — callers must not mutate them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class UploadedSourceArtifact:
    """Reference to a validated source EPUB in object storage.

    Matches the UploadedSourceArtifact contract defined in PIPELINE_CONTRACTS.md §1.
    storage_key is the canonical object key; callers must not derive it at this boundary.
    """

    artifact_id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    storage_key: str
    source_type: str = "epub"
    mime_type: str = "application/epub+zip"


@dataclass(frozen=True)
class ChapterRef:
    """A chapter entry from the EPUB spine.

    chapter_id — stable identifier from the EPUB manifest item id
    title      — chapter title extracted from the manifest or NCX/nav document
    order      — 0-based spine position
    """

    chapter_id: str
    title: str
    order: int


@dataclass(frozen=True)
class StructuralRef:
    """A non-text structural resource referenced by the EPUB.

    ref_type — one of: "image" | "stylesheet" | "footnote" | "link"
    href     — original EPUB href (relative to content root)
    """

    ref_type: str
    href: str


@dataclass(frozen=True)
class NormalizedDocument:
    """Authoritative document representation produced by the ingestion stage.

    Matches the NormalizedDocument contract defined in PIPELINE_CONTRACTS.md §1.
    This is the sole canonical output of ingestion and the input to segmentation.

    Fields:
        document_id          -- stable UUID generated at ingest time
        source_type          -- always "epub" for MVP
        title                -- book title from EPUB metadata
        author               -- book author(s) from EPUB metadata
        text                 -- full extracted UTF-8 text (chapters joined with double newlines)
        detected_language    -- BCP-47 language code (e.g. "en", "fr", "ja")
        detection_confidence -- float [0.0, 1.0] from language detector
        source_word_count    -- word count of the full extracted text
        chapter_refs         -- ordered list of ChapterRef (spine order)
        structural_refs      -- list of StructuralRef for non-text resources
        metadata             -- arbitrary key-value metadata from EPUB OPF
    """

    document_id: uuid.UUID
    source_type: str
    title: str
    author: str
    text: str
    detected_language: str
    detection_confidence: float
    source_word_count: int
    chapter_refs: List[ChapterRef] = field(default_factory=list)
    structural_refs: List[StructuralRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class IngestionError(Exception):
    """Base class for all ingestion stage errors."""


class DrmDetectedError(IngestionError):
    """Raised when a DRM-protected EPUB is detected.

    EPUB containers with META-INF/encryption.xml are rejected per POLICY-COPYRIGHT.
    """


class EpubParseError(IngestionError):
    """Raised when the EPUB cannot be parsed or is structurally invalid."""
