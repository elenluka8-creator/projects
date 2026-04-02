"""Language detector for the ingestion stage.

Wraps langdetect with a fixed seed for deterministic output.
Operates at the book level: receives a large text corpus and returns
a single (language_code, confidence) result.

Seed is configurable via LANGDETECT_SEED env var (default 42).
"""
from __future__ import annotations

import logging
import os

from app.logging.structured import log_structured

logger = logging.getLogger(__name__)

# Maximum characters fed to langdetect. Book-level accuracy is good beyond ~1000 chars;
# capping at 50 000 prevents pathological memory use on very large books.
LANG_DETECTION_TEXT_CAP = 50_000


class LanguageDetector:
    """Book-level language detector backed by langdetect.

    Instantiate once and reuse — seed is applied at construction time.
    """

    def __init__(self, seed: int | None = None) -> None:
        effective_seed = seed if seed is not None else int(os.getenv("LANGDETECT_SEED", "42"))
        try:
            from langdetect import DetectorFactory

            DetectorFactory.seed = effective_seed
        except ImportError as exc:
            raise ImportError(
                "langdetect is required for language detection. "
                "Install it via: pip install langdetect"
            ) from exc
        self._seed = effective_seed

    def detect(self, text: str) -> tuple[str, float]:
        """Detect the primary language of the given text.

        Args:
            text: UTF-8 text corpus (typically the full book text).

        Returns:
            Tuple of (BCP-47 language code, confidence [0.0, 1.0]).

        Raises:
            ValueError: if text is empty.
            RuntimeError: if detection fails.
        """
        if not text or not text.strip():
            raise ValueError("Cannot detect language from empty text.")

        sample = text[:LANG_DETECTION_TEXT_CAP]

        try:
            from langdetect import detect_langs

            results = detect_langs(sample)
        except Exception as exc:
            raise RuntimeError(f"Language detection failed: {exc}") from exc

        if not results:
            raise RuntimeError("Language detection returned no results.")

        top = results[0]
        lang_code: str = top.lang
        confidence: float = float(top.prob)

        log_structured(
            logger=logger,
            level=logging.DEBUG,
            message="language_detected",
            payload={
                "detected_language": lang_code,
                "confidence": round(confidence, 4),
                "sample_length": len(sample),
            },
        )

        return lang_code, confidence
