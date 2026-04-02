"""Translation stage data models.

Implements the pipeline contract from docs/PIPELINE_CONTRACTS.md §3 Translation.
All pipeline-contract types are frozen dataclasses — callers must not mutate them.
BatchResult and TranslationConfig are regular dataclasses (provider-internal use).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TranslationConfig:
    """Job-level translation configuration passed to the translation stage.

    Derived from Job model fields at orchestration time.
    """

    mode: str             # "translate" | "guided"
    target_language: str  # BCP-47 code (e.g. "en", "fr", "ja")
    source_language: str  # BCP-47 code (auto-detected or overridden)
    translation_style: str = "natural"  # "literal" | "natural"
    user_level: str = "B1"              # "A1"|"A2"|"B1"|"B2"|"C1"
    explanation_depth: str = "standard" # "minimal"|"standard"|"detailed"
    quality_tier: str = "standard"         # "express"|"standard"|"premium"


@dataclass(frozen=True)
class TranslatedSegment:
    """A translated paragraph-level unit.

    Contract fields per PIPELINE_CONTRACTS.md §3:
        id              -- Same stable ID as the source Segment.
        paragraph_id    -- Source paragraph ID (for reconstruction by formatting stage).
        chapter_ref     -- Chapter identifier from source Segment.
        structural_ref  -- Passed through unchanged from source Segment.
        original_text   -- Source paragraph text.
        translated_text -- Translation into target language.
        explanations    -- Cultural/idiomatic notes (Guided Mode only; empty list in Translate Mode).
    """

    id: str
    paragraph_id: str
    chapter_ref: str
    structural_ref: Optional[str]
    original_text: str
    translated_text: str
    explanations: List[str]


@dataclass(frozen=True)
class TranslatedSegmentCollection:
    """The output of the translation stage.

    Contract fields per PIPELINE_CONTRACTS.md §3:
        document_id         -- From the source SegmentCollection.
        mode                -- "translate" or "guided".
        translated_segments -- Ordered list of TranslatedSegment.
    """

    document_id: uuid.UUID
    mode: str
    translated_segments: List[TranslatedSegment]


@dataclass
class BatchResult:
    """Result returned by a provider for one translation batch.

    Not a pipeline contract type — internal to provider/stage coordination.
    """

    translated_segments: List[TranslatedSegment]
    tokens_in: int
    tokens_out: int
    new_terms: Dict[str, str]
    new_entities: Dict[str, Dict[str, Any]]
    chapter_summary: str
    latency_ms: float
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


# ── Exceptions ────────────────────────────────────────────────────────────────


class TranslationError(Exception):
    """Base class for all translation stage errors."""


class ProviderTransientError(TranslationError):
    """Raised for provider failures that are safe to retry (rate-limit, timeout, 5xx).

    Corresponds to failure_class = 'provider-transient' per DEC-007.
    """


class ContentDeterministicError(TranslationError):
    """Raised for failures caused by content or prompt issues — do not retry.

    Examples: persistent JSON parse failures, prompt too large.
    Corresponds to failure_class = 'content-deterministic' per DEC-007.
    """


class PromptBudgetExceededError(ContentDeterministicError):
    """Raised when the estimated prompt token count exceeds the configured budget."""


class ProviderBillingError(TranslationError):
    """Raised when the provider rejects the request due to insufficient account credits.

    This is a billing/account issue, not a content issue — it resolves once the
    provider account is topped up. Corresponds to failure_class = 'system'.
    """
