"""Pre-translation book analysis (preamble pass).

Runs a single LLM call over a strategic sample of the book before the main
translation loop begins. Produces an initial ConsistencyMemory populated with:
  - characters (name → translation, gender, role)
  - terminology (source_term → target_translation)
  - places (name → translation, type)
  - genre notes (injected as chapter_context_summary)

This module is a sub-step of the translation stage (DEC-003 compliance:
only the translation stage may invoke LLMs).

Design decisions:
  - Graceful degradation: any LLM or parse failure returns ConsistencyMemory.empty()
    so the main translation loop is never blocked.
  - Sample is bounded at MAX_PREAMBLE_CHARS to keep prompt cost predictable.
  - Skipped for books under MIN_WORDS_FOR_PREAMBLE (overhead not justified).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.logging.structured import log_structured
from app.pipeline.segmentation.models import SegmentCollection
from app.pipeline.translation.consistency import ConsistencyMemory
from app.pipeline.translation.models import TranslationConfig
from app.pipeline.translation.prompt_loader import load_prompt

if TYPE_CHECKING:
    from app.pipeline.translation.provider import AnthropicProvider

logger = logging.getLogger(__name__)

# Minimum estimated word count before a preamble pass is attempted.
MIN_WORDS_FOR_PREAMBLE: int = 5_000

# Hard character limit for the sample text sent to the LLM.
# ~15 000 tokens × 4 chars/token.
MAX_PREAMBLE_CHARS: int = 60_000

# Number of characters from the opening of the book included verbatim.
OPENING_CHARS: int = 12_000

# Max characters taken from the first paragraph of each subsequent chapter.
CHAPTER_SAMPLE_CHARS: int = 800


@dataclass
class PreambleResult:
    memory: ConsistencyMemory
    tokens_in: int
    tokens_out: int
    skipped: bool = False
    skip_reason: str = ""


def build_sample_text(collection: SegmentCollection) -> str:
    """Build a bounded sample text for the preamble LLM call.

    Strategy:
      1. Full opening: first OPENING_CHARS characters from the start of the book.
      2. Chapter samples: first CHAPTER_SAMPLE_CHARS characters of each chapter's
         first segment — gives the LLM visibility into how characters are introduced
         throughout the narrative without sending the full text.

    The combined result is hard-capped at MAX_PREAMBLE_CHARS.
    """
    if not collection.segments:
        return ""

    # Segments are ordered; first segment = start of book.
    opening_parts: List[str] = []
    opening_budget = OPENING_CHARS
    for seg in collection.segments:
        if opening_budget <= 0:
            break
        chunk = seg.original_text[:opening_budget]
        opening_parts.append(chunk)
        opening_budget -= len(chunk)

    opening = "\n\n".join(opening_parts)

    # Collect first segment per chapter (after the opening).
    seen_chapters: set = set()
    chapter_samples: List[str] = []
    used_in_opening = {s.id for s in collection.segments[: len(opening_parts)]}

    for seg in collection.segments:
        if seg.id in used_in_opening:
            seen_chapters.add(seg.chapter_ref)
            continue
        if seg.chapter_ref not in seen_chapters:
            seen_chapters.add(seg.chapter_ref)
            chapter_samples.append(seg.original_text[:CHAPTER_SAMPLE_CHARS])

    chapter_block = "\n\n---\n\n".join(chapter_samples)
    combined = opening
    if chapter_block:
        combined = combined + "\n\n---\n\n" + chapter_block

    return combined[:MAX_PREAMBLE_CHARS]


def _estimate_word_count(collection: SegmentCollection) -> int:
    return sum(len(s.original_text.split()) for s in collection.segments)


def analyze_preamble(
    collection: SegmentCollection,
    config: TranslationConfig,
    provider: "AnthropicProvider",
    prompts_root: str = "prompts",
) -> PreambleResult:
    """Run the preamble analysis LLM call.

    Returns a PreambleResult. On any failure, returns a result with
    ConsistencyMemory.empty() and skipped=True so the caller can proceed.
    """
    word_count = _estimate_word_count(collection)
    if word_count < MIN_WORDS_FOR_PREAMBLE:
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="preamble_skipped_short_book",
            payload={"word_count": word_count, "min": MIN_WORDS_FOR_PREAMBLE},
        )
        return PreambleResult(
            memory=ConsistencyMemory.empty(),
            tokens_in=0,
            tokens_out=0,
            skipped=True,
            skip_reason="book_too_short",
        )

    sample = build_sample_text(collection)
    if not sample:
        return PreambleResult(
            memory=ConsistencyMemory.empty(),
            tokens_in=0,
            tokens_out=0,
            skipped=True,
            skip_reason="empty_sample",
        )

    try:
        template = load_prompt("translation/analyze_preamble.yaml", prompts_root=prompts_root)
    except Exception as exc:
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="preamble_prompt_load_failed",
            payload={"error": str(exc)},
        )
        return PreambleResult(
            memory=ConsistencyMemory.empty(),
            tokens_in=0,
            tokens_out=0,
            skipped=True,
            skip_reason="prompt_load_failed",
        )

    from app.pipeline.translation.provider import _prompt_lang  # noqa: PLC0415

    user_message = template.render_user(
        source_language=_prompt_lang(config.source_language),
        target_language=_prompt_lang(config.target_language),
        sample_text=sample,
    )

    try:
        # Use a shorter timeout for preamble: if the LLM is slow, skip gracefully
        # rather than holding the job lease hostage for 10 minutes.
        raw, tokens_in, tokens_out, _cache_creation, _cache_read, latency_ms = provider._call_api(
            system=template.system,
            user=user_message,
            timeout_seconds=120.0,
        )
    except Exception as exc:
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="preamble_analysis_failed",
            payload={"error": str(exc)},
        )
        return PreambleResult(
            memory=ConsistencyMemory.empty(),
            tokens_in=0,
            tokens_out=0,
            skipped=True,
            skip_reason="llm_call_failed",
        )

    try:
        memory = _parse_preamble_response(raw)
    except Exception as exc:
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="preamble_parse_failed",
            payload={"error": str(exc), "raw_length": len(raw)},
        )
        return PreambleResult(
            memory=ConsistencyMemory.empty(),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            skipped=True,
            skip_reason="parse_failed",
        )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="preamble_analysis_completed",
        payload={
            "characters": len(memory.named_entity_registry),
            "terms": len(memory.terminology_map),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": round(latency_ms),
            "sample_chars": len(sample),
        },
    )

    return PreambleResult(memory=memory, tokens_in=tokens_in, tokens_out=tokens_out)


def _parse_preamble_response(raw: str) -> ConsistencyMemory:
    """Parse the LLM preamble response into a ConsistencyMemory."""
    import re  # noqa: PLC0415

    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{[\s\S]*\}", text)
        if brace:
            text = brace.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json  # type: ignore[import-untyped]
            data = repair_json(text, return_objects=True)
            if not isinstance(data, dict):
                raise ValueError("Repaired JSON is not a dict")
        except Exception as exc:
            raise ValueError(f"Cannot parse preamble JSON: {exc}") from exc

    memory = ConsistencyMemory.empty()

    def _to_dict(raw: Any) -> Dict[str, Any]:
        """Normalise a value that should be a dict but LLM may return as a list."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            out: Dict[str, Any] = {}
            for item in raw:
                if isinstance(item, dict):
                    key = item.get("name") or item.get("source") or item.get("original")
                    if key and isinstance(key, str):
                        out[key] = item
            return out
        return {}

    # --- Characters → named_entity_registry ---
    characters: Dict[str, Any] = _to_dict(data.get("characters"))
    new_entities: Dict[str, Any] = {}
    for name, meta in characters.items():
        if not isinstance(meta, dict):
            continue
        new_entities[name] = {
            "translation": meta.get("translation", name),
            "type": "person",
            "gender": meta.get("gender", "none"),
            "role": meta.get("role", ""),
        }

    # --- Places → named_entity_registry ---
    places: Dict[str, Any] = _to_dict(data.get("places"))
    for name, meta in places.items():
        if not isinstance(meta, dict):
            continue
        new_entities[name] = {
            "translation": meta.get("translation", name),
            "type": meta.get("type", "place"),
            "gender": "none",
        }

    if new_entities:
        memory.update(new_terms={}, new_entities=new_entities, chapter_summary="")

    # --- Terminology → terminology_map ---
    raw_terminology = data.get("terminology")
    terminology: Dict[str, str] = raw_terminology if isinstance(raw_terminology, dict) else {}
    new_terms = {k: v for k, v in terminology.items() if isinstance(v, str)}
    if new_terms:
        memory.update(new_terms=new_terms, new_entities={}, chapter_summary="")

    # --- Genre notes → chapter_context_summary ---
    genre_notes: str = data.get("genre_notes") or ""
    if genre_notes:
        memory.update(new_terms={}, new_entities={}, chapter_summary=genre_notes)

    return memory
