"""Translation stage entry point.

Public API:
  translate(collection, config, provider, ...) -> TranslatedSegmentCollection

Responsibilities:
- Iterate over batch hints from SegmentCollection.batch_planning
- Call provider.translate_batch() for each batch
- Accumulate consistency memory across batches
- Run non-LLM quality checks per batch (DEC-005)
- Invoke optional per-batch callback for orchestration hooks (DB, cost, telemetry)
- Return the full TranslatedSegmentCollection

Out of scope: DB writes, cost accounting, timeline events, retries
(all handled by orchestration layer via on_batch_complete callback),
LLM provider selection.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from app.logging.structured import log_structured
from app.pipeline.segmentation.models import Segment, SegmentCollection
from app.pipeline.translation.consistency import ConsistencyMemory
from app.pipeline.translation.models import (
    BatchResult,
    TranslatedSegment,
    TranslatedSegmentCollection,
    TranslationConfig,
    TranslationError,
)
from app.pipeline.translation.preamble import PreambleResult, analyze_preamble
from app.pipeline.translation.provider import TranslationProviderProtocol
from app.pipeline.translation.quality import check_batch_quality

logger = logging.getLogger(__name__)

# Type alias for the per-batch callback used by orchestration.
# Signature: on_batch_complete(batch_index, batch_result)
OnBatchComplete = Callable[[int, BatchResult], None]

# Callback invoked after the preamble analysis LLM call completes.
# Signature: on_preamble_complete(preamble_result)
OnPreambleComplete = Callable[[PreambleResult], None]


def translate(
    collection: SegmentCollection,
    config: TranslationConfig,
    provider: TranslationProviderProtocol,
    consistency_memory: Optional[ConsistencyMemory] = None,
    on_batch_complete: Optional[OnBatchComplete] = None,
    on_preamble_complete: Optional[OnPreambleComplete] = None,
    prompts_root: str = "prompts",
) -> TranslatedSegmentCollection:
    """Run the translation stage for a full SegmentCollection.

    Processes batches in order using the batch_boundary_hints from the
    SegmentCollection batch_planning metadata.

    Args:
        collection:           Output of the segmentation stage.
        config:               Job-level translation configuration.
        provider:             Provider adapter (AnthropicProvider or FakeProvider in tests).
        consistency_memory:   Pre-populated memory (for resuming a job); starts empty if None.
        on_batch_complete:    Optional callback invoked after each successful batch.
                              Receives (batch_index, BatchResult). Used by the orchestrator
                              to record DB checkpoints and cost entries without coupling
                              stage logic to DB concerns.
        on_preamble_complete: Optional callback invoked after the preamble analysis call.
                              Receives PreambleResult. Used by the orchestrator to record
                              cost and emit a timeline event.
        prompts_root:         Root directory for prompts (overridable in tests).

    Returns:
        TranslatedSegmentCollection with all segments translated.

    Raises:
        TranslationError: Propagated from provider (provider-transient or
                          content-deterministic) after retries are exhausted.
    """
    if not collection.segments:
        raise TranslationError(
            f"SegmentCollection for document {collection.document_id} has no segments."
        )

    memory = consistency_memory or ConsistencyMemory.empty()

    # --- Preamble analysis pass (pre-populates ConsistencyMemory before batch 0) ---
    # Only runs when no pre-existing memory was passed (first run, not a resume).
    if memory.is_empty():
        from app.pipeline.translation.provider import AnthropicProvider  # noqa: PLC0415
        if isinstance(provider, AnthropicProvider):
            preamble_result = analyze_preamble(
                collection=collection,
                config=config,
                provider=provider,
                prompts_root=prompts_root,
            )
            if not preamble_result.skipped:
                # Merge preamble memory into the (empty) job memory.
                memory.terminology_map.update(preamble_result.memory.terminology_map)
                memory.named_entity_registry.update(preamble_result.memory.named_entity_registry)
                memory.term_hits.update(preamble_result.memory.term_hits)
                memory.entity_hits.update(preamble_result.memory.entity_hits)
                if preamble_result.memory.chapter_context_summary:
                    memory.chapter_context_summary = preamble_result.memory.chapter_context_summary
            if on_preamble_complete is not None:
                on_preamble_complete(preamble_result)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="translation_started",
        payload={
            "document_id": str(collection.document_id),
            "mode": config.mode,
            "segment_count": len(collection.segments),
            "batch_count": collection.batch_planning.estimated_batch_count,
            "target_language": config.target_language,
            "source_language": config.source_language,
        },
    )

    seg_map = {s.id: s for s in collection.segments}
    all_translated: list[TranslatedSegment] = []

    for hint in collection.batch_planning.batch_boundary_hints:
        batch_segments: list[Segment] = [
            seg_map[sid] for sid in hint.segment_ids if sid in seg_map
        ]
        if not batch_segments:
            continue

        result = provider.translate_batch(
            segments=batch_segments,
            config=config,
            consistency_memory=memory,
            batch_index=hint.batch_index,
        )

        memory.update(
            new_terms=result.new_terms,
            new_entities=result.new_entities,
            chapter_summary=result.chapter_summary,
        )

        issues = check_batch_quality(
            segments=batch_segments,
            translated=result.translated_segments,
            source_lang=config.source_language,
            target_lang=config.target_language,
        )
        for issue in issues:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="translation_quality_issue",
                payload={
                    "check": issue.check_name,
                    "segment_id": issue.segment_id,
                    "detail": issue.message,
                    "batch_index": hint.batch_index,
                },
            )

        all_translated.extend(result.translated_segments)

        if on_batch_complete is not None:
            on_batch_complete(hint.batch_index, result)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="translation_completed",
        payload={
            "document_id": str(collection.document_id),
            "translated_count": len(all_translated),
        },
    )

    return TranslatedSegmentCollection(
        document_id=collection.document_id,
        mode=config.mode,
        translated_segments=all_translated,
    )
