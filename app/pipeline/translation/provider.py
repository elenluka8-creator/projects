"""Translation provider adapter for the translation stage.

Defines the TranslationProviderProtocol interface and the AnthropicProvider
implementation (the only LLM boundary in the pipeline per DEC-003).

Rules (DEC-003):
- Only this module may import or call the Anthropic client.
- Model name comes from TRANSLATION_MODEL env var, never hardcoded.
- Retries are explicit and bounded (DEC-007).
- Provider payloads contain only current batch text + bounded context (DEC-004).
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from typing import List, Optional, Protocol, runtime_checkable

from app.logging.structured import log_structured
from app.pipeline.segmentation.models import Segment
from app.pipeline.translation.consistency import ConsistencyMemory
from app.pipeline.translation.models import (
    BatchResult,
    ContentDeterministicError,
    PromptBudgetExceededError,
    ProviderBillingError,
    ProviderTransientError,
    TranslationConfig,
    TranslatedSegment,
)
from app.pipeline.translation.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_PROVIDER_NAME = "anthropic"

# ── Configurable limits ───────────────────────────────────────────────────────

MAX_BATCH_RETRIES: int = int(os.environ.get("TRANSLATION_MAX_RETRIES", "3"))
# Default 16k: guided mode + large batches can exceed 8k output; Railway may set 32768.
MAX_TOKENS_RESPONSE: int = int(os.environ.get("TRANSLATION_MAX_TOKENS_RESPONSE", "16384"))
MAX_PROMPT_CHARS: int = int(os.environ.get("TRANSLATION_MAX_PROMPT_CHARS", "50000"))

# Retry back-off base delays in seconds.
_RETRY_DELAYS = [1.0, 2.0, 4.0]

_BILLING_ERROR_PHRASES = (
    "credit balance is too low",
    "insufficient credits",
    "billing",
    "payment required",
    "upgrade or purchase",
)


def _is_billing_error(exc: Exception) -> bool:
    """Return True if the exception message indicates an account billing/credit issue."""
    msg = str(exc).lower()
    return any(phrase in msg for phrase in _BILLING_ERROR_PHRASES)

# Style notes injected into the prompt.
_STYLE_NOTES = {
    "literal": (
        "Stay as close as possible to the original word order and phrasing. "
        "Prefer direct word-for-word equivalents. Keep sentence structure intact "
        "even if the result sounds slightly formal or unidiomatic in the target language."
    ),
    "natural": (
        "Prioritise fluency and readability. Restructure sentences freely, "
        "use idiomatic target-language expressions, and rephrase as needed -- "
        "as long as the meaning and tone are fully preserved."
    ),
}

# Translation vocabulary level: how to calibrate the target-language text.
_LEVEL_NOTES = {
    "A1": "Translate to very simple vocabulary. Use only the most common everyday words. Avoid complex sentence structures.",
    "A2": "Translate to simple vocabulary. Avoid rare or technical terms. Keep sentences short and clear.",
    "B1": "Translate to standard vocabulary suitable for an intermediate reader. Occasional uncommon words are fine.",
    "B2": "Translate with varied vocabulary. Literary terms and less common words are acceptable.",
    "C1": "Translate with advanced vocabulary, fully preserving the author's stylistic register and phrasing.",
}

# Explanation behaviour in Guided mode: how many notes and what to focus on.
_LEVEL_EXPLANATION_NOTES = {
    "A1": (
        "Reader is a beginner. Explain every non-trivial word, grammar pattern, and idiom. "
        "Include basic grammar notes (verb tenses, prepositions, articles, etc.)."
    ),
    "A2": (
        "Reader is at elementary level. Explain most non-obvious words, idioms, "
        "and grammar patterns. Keep explanations concise and practical."
    ),
    "B1": (
        "Reader is intermediate. Explain idioms, cultural references, "
        "and non-obvious grammar constructions. Skip very common vocabulary."
    ),
    "B2": (
        "Reader is upper-intermediate. Focus on idioms, literary devices, "
        "and cultural or historical references. Skip routine grammar."
    ),
    "C1": (
        "Reader is advanced. Use minimal explanations -- only for rare idioms, "
        "cultural references, or highly specific vocabulary. "
        "Skip obvious grammar and common expressions entirely."
    ),
}

# Human-readable language names sent to the LLM in prompts.
# Where a language has script ambiguity (e.g. Serbian: Cyrillic vs Latin),
# the name includes an explicit script instruction so the model never
# defaults to the wrong script.
_LANGUAGE_PROMPT_NAMES: dict[str, str] = {
    "en": "English",
    "ru": "Russian",
    "sr": "Serbian (Cyrillic script only — never use Latin letters)",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "tr": "Turkish",
    "nl": "Dutch",
    "pl": "Polish",
}


def _prompt_lang(code: str) -> str:
    """Return the LLM-facing language label for a BCP-47 code."""
    return _LANGUAGE_PROMPT_NAMES.get(code, code)


# Explanation depth notes for Guided Mode.
_DEPTH_NOTES = {
    "minimal": (
        "Maximum 1 short note per paragraph. "
        "Include only explanations for idioms or references that would be completely opaque without them."
    ),
    "standard": (
        "1-2 notes per paragraph on average. "
        "Cover idioms, cultural references, and non-obvious literary devices."
    ),
    "detailed": (
        "3-5 notes per paragraph. "
        "Cover grammar constructions, vocabulary with etymology, idioms, "
        "sentence structure patterns, and cultural context. Be thorough."
    ),
}


@runtime_checkable
class TranslationProviderProtocol(Protocol):
    """Interface that provider implementations must satisfy."""

    def translate_batch(
        self,
        segments: List[Segment],
        config: TranslationConfig,
        consistency_memory: ConsistencyMemory,
        batch_index: int,
    ) -> BatchResult:
        ...


class AnthropicProvider:
    """Anthropic Claude provider adapter.

    A single instance is safe to reuse across batches within one job run.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        prompts_root: str = "prompts",
    ) -> None:
        self._model = (
            model
            or os.environ.get("TRANSLATION_MODEL", _DEFAULT_MODEL)
        )
        self._prompts_root = prompts_root
        # Client instantiated lazily to allow import without ANTHROPIC_API_KEY.
        self._client = None

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            import anthropic  # noqa: PLC0415
            self._client = anthropic.Anthropic(
                api_key=os.environ["ANTHROPIC_API_KEY"]
            )
        return self._client

    @property
    def model(self) -> str:
        return self._model

    def translate_batch(
        self,
        segments: List[Segment],
        config: TranslationConfig,
        consistency_memory: ConsistencyMemory,
        batch_index: int,
    ) -> BatchResult:
        """Translate one batch of segments.

        Implements retry logic per DEC-007:
          - provider-transient errors retried up to MAX_BATCH_RETRIES times
          - content-deterministic errors raised immediately
          - JSON parse errors retried once; second failure → ContentDeterministicError

        Args:
            segments:           Segments for this batch.
            config:             Job-level translation config.
            consistency_memory: Accumulated consistency state.
            batch_index:        0-based batch index (for logging).

        Returns:
            BatchResult with translated segments and token/latency metadata.
        """
        prompt_template = self._load_prompt(config.mode)
        user_message = self._build_user_message(
            prompt_template, segments, config, consistency_memory
        )

        if len(user_message) > MAX_PROMPT_CHARS:
            raise PromptBudgetExceededError(
                f"Prompt size {len(user_message)} chars exceeds "
                f"budget {MAX_PROMPT_CHARS} chars."
            )

        parse_failures = 0
        last_exc: Optional[Exception] = None

        for attempt in range(MAX_BATCH_RETRIES + 1):
            try:
                raw, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms = self._call_api(
                    system=prompt_template.system,
                    user=user_message,
                )
                parsed = self._parse_response(raw)
                translated = self._map_translations(
                    segments, parsed, config, batch_index
                )
                raw_new_terms = parsed.get("new_terms", {})
                consistency_updates = raw_new_terms if isinstance(raw_new_terms, dict) else {}
                raw_new_entities = parsed.get("new_entities", {})
                new_entities = raw_new_entities if isinstance(raw_new_entities, dict) else {}
                chapter_summary = parsed.get("chapter_summary", "")

                log_structured(
                    logger=logger,
                    level=logging.INFO,
                    message="provider_batch_ok",
                    payload={
                        "batch_index": batch_index,
                        "segment_count": len(segments),
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cache_creation_tokens": cache_creation_tokens,
                        "cache_read_tokens": cache_read_tokens,
                        "latency_ms": round(latency_ms, 1),
                        "model": self._model,
                        "attempt": attempt,
                    },
                )

                return BatchResult(
                    translated_segments=translated,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cache_creation_tokens=cache_creation_tokens,
                    cache_read_tokens=cache_read_tokens,
                    new_terms=consistency_updates,
                    new_entities=new_entities,
                    chapter_summary=chapter_summary,
                    latency_ms=latency_ms,
                )

            except ContentDeterministicError:
                raise

            except _JsonParseError as exc:
                parse_failures += 1
                last_exc = exc
                if parse_failures >= 4:
                    raise ContentDeterministicError(
                        f"JSON parse failed {parse_failures} times for "
                        f"batch {batch_index}: {exc}"
                    ) from exc
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="provider_json_parse_retry",
                    payload={"batch_index": batch_index, "attempt": attempt},
                )
                # Short retry for parse failures.
                time.sleep(0.5)
                continue

            except ProviderTransientError as exc:
                last_exc = exc
                if attempt == MAX_BATCH_RETRIES:
                    raise
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                jitter = random.uniform(0, delay * 0.2)
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="provider_transient_retry",
                    payload={
                        "batch_index": batch_index,
                        "attempt": attempt,
                        "delay_s": round(delay + jitter, 2),
                    },
                )
                time.sleep(delay + jitter)

        # Should not be reachable, but satisfy type checker.
        raise ProviderTransientError(
            f"Provider failed after {MAX_BATCH_RETRIES} retries."
        ) from last_exc

    def _load_prompt(self, mode: str):  # type: ignore[return]
        path = (
            "translation/translate_batch.yaml"
            if mode == "translate"
            else "guided_explanations/guided_batch.yaml"
        )
        return load_prompt(path, prompts_root=self._prompts_root)

    def _build_user_message(
        self,
        template,
        segments: List[Segment],
        config: TranslationConfig,
        memory: ConsistencyMemory,
    ) -> str:
        segments_json = json.dumps(
            [{"id": s.id, "text": s.original_text} for s in segments],
            ensure_ascii=False,
            indent=2,
        )
        consistency_section = memory.to_context_string()
        consistency_block = (
            f"Translation consistency context:\n{consistency_section}"
            if consistency_section
            else "(No consistency context yet — this is the first batch.)"
        )

        depth_note = (
            _DEPTH_NOTES.get(config.explanation_depth, _DEPTH_NOTES["standard"])
            if config.mode == "guided"
            else ""
        )

        # In guided mode, compose translation-level note with explanation-behaviour
        # note so the LLM receives both signals in a single field.
        level_translation_note = _LEVEL_NOTES.get(config.user_level, _LEVEL_NOTES["B1"])
        if config.mode == "guided":
            level_expl_note = _LEVEL_EXPLANATION_NOTES.get(
                config.user_level, _LEVEL_EXPLANATION_NOTES["B1"]
            )
            user_level_notes = f"{level_translation_note} {level_expl_note}"
        else:
            user_level_notes = level_translation_note

        return template.render_user(
            source_language=_prompt_lang(config.source_language),
            target_language=_prompt_lang(config.target_language),
            translation_style=config.translation_style,
            translation_style_notes=_STYLE_NOTES.get(
                config.translation_style, _STYLE_NOTES["natural"]
            ),
            user_level=config.user_level,
            user_level_notes=user_level_notes,
            consistency_context=consistency_block,
            depth_note=depth_note,
            segments_json=segments_json,
        )

    def _call_api(
        self,
        system: str,
        user: str,
        timeout_seconds: Optional[float] = None,
    ):
        """Call the Anthropic Messages API.

        Returns:
            (text, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms)
        """
        client = self._get_client()
        start = time.time()
        try:
            import anthropic  # noqa: PLC0415
            # Default timeout must exceed max generation time: at ~60 tok/s,
            # 32768 tokens takes ~546s. Configurable via TRANSLATION_REQUEST_TIMEOUT.
            _default_timeout = float(os.environ.get("TRANSLATION_REQUEST_TIMEOUT", "600"))
            kwargs = dict(
                model=self._model,
                max_tokens=MAX_TOKENS_RESPONSE,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                timeout=timeout_seconds if timeout_seconds is not None else _default_timeout,
            )
            response = client.messages.create(**kwargs)
        except anthropic.RateLimitError as exc:
            raise ProviderTransientError(f"Rate limit: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code == 529:
                raise ProviderTransientError(f"Provider 5xx ({exc.status_code}): {exc}") from exc
            if exc.status_code == 400 and _is_billing_error(exc):
                raise ProviderBillingError(f"Provider billing error ({exc.status_code}): {exc}") from exc
            raise ContentDeterministicError(f"Provider API error ({exc.status_code}): {exc}") from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderTransientError(f"Provider timeout: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderTransientError(f"Provider connection error: {exc}") from exc

        latency_ms = (time.time() - start) * 1000
        text = response.content[0].text
        usage = response.usage
        tokens_in = usage.input_tokens
        tokens_out = usage.output_tokens
        cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
        return text, tokens_in, tokens_out, cache_creation_tokens, cache_read_tokens, latency_ms

    def _parse_response(self, raw: str) -> dict:
        """Extract and parse the JSON object from the LLM response.

        Strips markdown fences if present. Falls back to json-repair for
        common LLM JSON formatting errors. Raises _JsonParseError on failure.
        """
        text = raw.strip()

        # Strip markdown code fences: ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if fence_match:
            text = fence_match.group(1)
        else:
            # Extract first top-level JSON object
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: attempt repair for common LLM JSON issues (missing commas,
        # unescaped quotes, truncated output, trailing commas).
        try:
            from json_repair import repair_json  # type: ignore[import-untyped]
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict):
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="provider_json_repaired",
                    payload={"original_length": len(raw)},
                )
                return repaired
        except Exception:
            pass

        raise _JsonParseError(
            f"JSON parse failed and repair unsuccessful for response of length {len(raw)}"
        )

    def _map_translations(
        self,
        segments: List[Segment],
        parsed: dict,
        config: TranslationConfig,
        batch_index: int,
    ) -> List[TranslatedSegment]:
        """Map parsed JSON translations back to TranslatedSegment objects.

        If the LLM omits a segment, its original text is used as a fallback
        and a warning is logged. This ensures no segments are ever lost.
        """
        translations_by_id = {
            t["id"]: t
            for t in parsed.get("translations", [])
            if isinstance(t, dict) and "id" in t
        }

        result = []
        for seg in segments:
            t = translations_by_id.get(seg.id)
            if t is None:
                log_structured(
                    logger=logger,
                    level=logging.WARNING,
                    message="provider_missing_segment",
                    payload={"segment_id": seg.id, "batch_index": batch_index},
                )
                translated_text = seg.original_text
                explanations = []
            else:
                translated_text = str(t.get("translated_text", seg.original_text))
                # Normalise the LLM's explanations field to a list of strings.
                # The LLM occasionally returns a plain string instead of a JSON
                # array (e.g. "explanations": "«улыбнулась» — smiled").
                # Iterating over a bare string yields individual characters, so
                # we must wrap it in a list before the list-comprehension below.
                raw_expl = t.get("explanations", [])
                if isinstance(raw_expl, str):
                    # Split on newlines so a multi-note string from the LLM
                    # (e.g. "note1\nnote2\nnote3") yields separate items.
                    raw_expl = [line.strip() for line in raw_expl.splitlines() if line.strip()] if raw_expl.strip() else []
                elif not isinstance(raw_expl, list):
                    raw_expl = []
                explanations = (
                    [str(e) for e in raw_expl if str(e).strip()]
                    if config.mode == "guided"
                    else []
                )

            result.append(
                TranslatedSegment(
                    id=seg.id,
                    paragraph_id=seg.paragraph_id,
                    chapter_ref=seg.chapter_ref,
                    structural_ref=seg.structural_ref,
                    original_text=seg.original_text,
                    translated_text=translated_text,
                    explanations=explanations,
                )
            )
        return result


class _JsonParseError(Exception):
    """Internal: JSON parsing failed — used to trigger parse-retry logic."""
