"""Tests for app.pipeline.translation.

All tests use FakeProvider — no real Anthropic API calls are made.
FakeProvider returns realistic structured responses so the full parsing path
(JSON serialisation/deserialisation inside provider.py) is exercised indirectly
via the stage and consistency logic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.pipeline.segmentation.models import (
    BatchBoundaryHint,
    BatchPlanning,
    Segment,
    SegmentCollection,
)
from app.pipeline.translation.consistency import ConsistencyMemory
from app.pipeline.translation.models import (
    BatchResult,
    ContentDeterministicError,
    ProviderTransientError,
    TranslatedSegment,
    TranslatedSegmentCollection,
    TranslationConfig,
    TranslationError,
)
from app.pipeline.translation.provider import TranslationProviderProtocol
from app.pipeline.translation.quality import QualityIssue, check_batch_quality
from app.pipeline.translation.stage import translate


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_segment(
    seg_id: str,
    text: str,
    chapter_ref: str = "ch-1",
    para_idx: int = 0,
) -> Segment:
    return Segment(
        id=seg_id,
        paragraph_id=seg_id,
        chapter_ref=chapter_ref,
        structural_ref=None,
        original_text=text,
        token_estimate=len(text) // 4 or 1,
    )


def _make_collection(
    segments: List[Segment],
    mode: str = "translate",
) -> SegmentCollection:
    doc_id = uuid.uuid4()
    batch_segments = [s.id for s in segments]
    hint = BatchBoundaryHint(
        batch_index=0,
        segment_ids=batch_segments,
        token_total=sum(s.token_estimate for s in segments),
        chapter_ref=segments[0].chapter_ref if segments else "ch-1",
    )
    planning = BatchPlanning(
        chapter_boundaries={"ch-1": 0},
        batch_boundary_hints=[hint],
        estimated_batch_count=1,
    )
    return SegmentCollection(
        document_id=doc_id,
        mode=mode,
        segments=segments,
        batch_planning=planning,
    )


def _default_config(
    mode: str = "translate",
    source_language: str = "fr",
    target_language: str = "en",
) -> TranslationConfig:
    return TranslationConfig(
        mode=mode,
        target_language=target_language,
        source_language=source_language,
        translation_style="natural",
        user_level="B1",
        explanation_depth="standard",
    )


class FakeProvider:
    """Test double for TranslationProviderProtocol.

    Returns deterministic translations of the form '<original_text> [translated]'.
    Supports configurable explanations (Guided Mode) and term/entity injection.
    """

    def __init__(
        self,
        prefix: str = "[translated]",
        new_terms: Optional[Dict[str, str]] = None,
        new_entities: Optional[Dict] = None,
        explanations: Optional[List[str]] = None,
        fail_once_transient: bool = False,
        fail_always_deterministic: bool = False,
        fail_twice_json: bool = False,
    ):
        self._prefix = prefix
        self._new_terms = new_terms or {}
        self._new_entities = new_entities or {}
        self._explanations = explanations or []
        self._fail_once_transient = fail_once_transient
        self._fail_always_deterministic = fail_always_deterministic
        self._fail_twice_json = fail_twice_json
        self._call_count = 0

    def translate_batch(
        self,
        segments: List[Segment],
        config: TranslationConfig,
        consistency_memory: ConsistencyMemory,
        batch_index: int,
    ) -> BatchResult:
        self._call_count += 1

        if self._fail_always_deterministic:
            raise ContentDeterministicError("Simulated deterministic error")

        if self._fail_once_transient and self._call_count == 1:
            raise ProviderTransientError("Simulated transient error (first call)")

        translated = [
            TranslatedSegment(
                id=s.id,
                paragraph_id=s.paragraph_id,
                chapter_ref=s.chapter_ref,
                structural_ref=s.structural_ref,
                original_text=s.original_text,
                translated_text=f"{s.original_text} {self._prefix}",
                explanations=(
                    self._explanations if config.mode == "guided" else []
                ),
            )
            for s in segments
        ]

        return BatchResult(
            translated_segments=translated,
            tokens_in=sum(s.token_estimate for s in segments),
            tokens_out=sum(s.token_estimate for s in segments) + 5,
            new_terms=self._new_terms,
            new_entities=self._new_entities,
            chapter_summary="Test chapter summary.",
            latency_ms=10.0,
        )


# ── Stage tests ────────────────────────────────────────────────────────────


class TestTranslateStage:

    def test_basic_translate_mode(self):
        segs = [_make_segment("s1", "Bonjour le monde")]
        collection = _make_collection(segs)
        result = translate(collection, _default_config(), FakeProvider())

        assert isinstance(result, TranslatedSegmentCollection)
        assert len(result.translated_segments) == 1
        ts = result.translated_segments[0]
        assert ts.id == "s1"
        assert "Bonjour le monde" in ts.translated_text
        assert ts.original_text == "Bonjour le monde"
        assert ts.explanations == []

    def test_guided_mode_includes_explanations(self):
        segs = [_make_segment("s1", "Il était une fois")]
        collection = _make_collection(segs, mode="guided")
        config = _default_config(mode="guided")
        provider = FakeProvider(explanations=["Idiom: 'Once upon a time'"])

        result = translate(collection, config, provider)

        ts = result.translated_segments[0]
        assert ts.explanations == ["Idiom: 'Once upon a time'"]

    def test_translate_mode_has_empty_explanations(self):
        segs = [_make_segment("s1", "Bonjour")]
        collection = _make_collection(segs)
        provider = FakeProvider(explanations=["Should not appear"])

        result = translate(collection, _default_config(mode="translate"), provider)

        assert result.translated_segments[0].explanations == []

    def test_all_segments_present_in_output(self):
        segs = [
            _make_segment(f"s{i}", f"Paragraph {i}") for i in range(10)
        ]
        collection = _make_collection(segs)
        result = translate(collection, _default_config(), FakeProvider())

        ids_in = {s.id for s in segs}
        ids_out = {ts.id for ts in result.translated_segments}
        assert ids_in == ids_out

    def test_document_id_and_mode_propagated(self):
        segs = [_make_segment("s1", "Hello")]
        collection = _make_collection(segs, mode="guided")
        result = translate(collection, _default_config(mode="guided"), FakeProvider())

        assert result.document_id == collection.document_id
        assert result.mode == "guided"

    def test_empty_collection_raises(self):
        segs: List[Segment] = []
        collection = _make_collection(segs)
        with pytest.raises(TranslationError, match="no segments"):
            translate(collection, _default_config(), FakeProvider())

    def test_multiple_batches_all_translated(self):
        doc_id = uuid.uuid4()
        segs = [_make_segment(f"s{i}", f"Phrase {i}") for i in range(4)]
        hint0 = BatchBoundaryHint(0, ["s0", "s1"], 10, "ch-1")
        hint1 = BatchBoundaryHint(1, ["s2", "s3"], 10, "ch-1")
        planning = BatchPlanning(
            chapter_boundaries={"ch-1": 0},
            batch_boundary_hints=[hint0, hint1],
            estimated_batch_count=2,
        )
        collection = SegmentCollection(
            document_id=doc_id, mode="translate", segments=segs, batch_planning=planning
        )
        result = translate(collection, _default_config(), FakeProvider())

        assert len(result.translated_segments) == 4

    def test_on_batch_complete_callback_called(self):
        segs = [_make_segment("s1", "Hello")]
        collection = _make_collection(segs)
        callbacks: List[int] = []

        def cb(batch_idx, batch_result):
            callbacks.append(batch_idx)

        translate(collection, _default_config(), FakeProvider(), on_batch_complete=cb)
        assert callbacks == [0]

    def test_on_batch_complete_called_per_batch(self):
        doc_id = uuid.uuid4()
        segs = [_make_segment(f"s{i}", f"Para {i}") for i in range(4)]
        hint0 = BatchBoundaryHint(0, ["s0", "s1"], 10, "ch-1")
        hint1 = BatchBoundaryHint(1, ["s2", "s3"], 10, "ch-1")
        planning = BatchPlanning(
            chapter_boundaries={"ch-1": 0},
            batch_boundary_hints=[hint0, hint1],
            estimated_batch_count=2,
        )
        collection = SegmentCollection(
            document_id=doc_id, mode="translate", segments=segs, batch_planning=planning
        )
        called_with: List[int] = []
        translate(
            collection,
            _default_config(),
            FakeProvider(),
            on_batch_complete=lambda idx, r: called_with.append(idx),
        )
        assert called_with == [0, 1]

    def test_provider_transient_error_propagates(self):
        segs = [_make_segment("s1", "Test")]
        collection = _make_collection(segs)
        provider = FakeProvider(fail_always_deterministic=False)

        class AlwaysTransient:
            def translate_batch(self, segments, config, consistency_memory, batch_index):
                raise ProviderTransientError("Always fails")

        with pytest.raises(ProviderTransientError):
            translate(collection, _default_config(), AlwaysTransient())

    def test_content_deterministic_error_propagates(self):
        segs = [_make_segment("s1", "Test")]
        collection = _make_collection(segs)

        class AlwaysDeterministic:
            def translate_batch(self, segments, config, consistency_memory, batch_index):
                raise ContentDeterministicError("Deterministic failure")

        with pytest.raises(ContentDeterministicError):
            translate(collection, _default_config(), AlwaysDeterministic())


# ── Consistency memory tests ───────────────────────────────────────────────


class TestConsistencyMemory:

    def test_empty_memory_is_empty(self):
        m = ConsistencyMemory.empty()
        assert m.is_empty()

    def test_update_adds_terms(self):
        m = ConsistencyMemory.empty()
        m.update({"bonjour": "hello"}, {}, "A greeting scene.")
        assert m.terminology_map["bonjour"] == "hello"

    def test_update_adds_entities(self):
        m = ConsistencyMemory.empty()
        m.update({}, {"Marie": {"translation": "Mary", "type": "character"}}, "")
        assert "Marie" in m.named_entity_registry
        assert m.named_entity_registry["Marie"]["translation"] == "Mary"

    def test_chapter_summary_updated(self):
        m = ConsistencyMemory.empty()
        m.update({}, {}, "Opening chapter in Paris.")
        assert m.chapter_context_summary == "Opening chapter in Paris."

    def test_context_string_includes_terms(self):
        m = ConsistencyMemory.empty()
        m.update({"château": "castle"}, {}, "")
        ctx = m.to_context_string()
        assert "château" in ctx
        assert "castle" in ctx

    def test_context_string_includes_entities(self):
        m = ConsistencyMemory.empty()
        m.update({}, {"Jean Valjean": {"translation": "Jean Valjean", "type": "character"}}, "")
        ctx = m.to_context_string()
        assert "Jean Valjean" in ctx

    def test_context_string_bounded(self):
        m = ConsistencyMemory.empty()
        m.update(
            {f"term_{i}": f"translation_{i}" for i in range(200)},
            {},
            "Very long summary " * 100,
        )
        ctx = m.to_context_string()
        assert len(ctx) <= 2000  # _MAX_CONTEXT_CHARS (includes ellipsis when truncated)

    def test_consistency_accumulated_across_batches(self):
        segs = [_make_segment("s1", "Bonjour")]
        collection = _make_collection(segs)
        provider = FakeProvider(
            new_terms={"bonjour": "hello"},
            new_entities={"Marie": {"translation": "Mary", "type": "character"}},
        )
        memory = ConsistencyMemory.empty()
        translate(collection, _default_config(), provider, consistency_memory=memory)

        assert "bonjour" in memory.terminology_map
        assert "Marie" in memory.named_entity_registry


# ── Quality check tests ────────────────────────────────────────────────────


class TestQualityChecks:

    def _ts(self, seg: Segment, translated_text: str) -> TranslatedSegment:
        return TranslatedSegment(
            id=seg.id,
            paragraph_id=seg.paragraph_id,
            chapter_ref=seg.chapter_ref,
            structural_ref=seg.structural_ref,
            original_text=seg.original_text,
            translated_text=translated_text,
            explanations=[],
        )

    def test_no_issues_for_good_translation(self):
        seg = _make_segment("s1", "Bonjour tout le monde")
        ts = self._ts(seg, "Hello everyone in the world")
        issues = check_batch_quality([seg], [ts], "fr", "en")
        assert issues == []

    def test_untranslated_segment_detected(self):
        seg = _make_segment("s1", "Bonjour le monde")
        ts = self._ts(seg, "Bonjour le monde")
        issues = check_batch_quality([seg], [ts], "fr", "en")
        names = [i.check_name for i in issues]
        assert "untranslated_segment" in names

    def test_untranslated_not_flagged_for_same_language(self):
        seg = _make_segment("s1", "Hello world")
        ts = self._ts(seg, "Hello world")
        issues = check_batch_quality([seg], [ts], "en", "en")
        assert not any(i.check_name == "untranslated_segment" for i in issues)

    def test_short_translation_detected(self):
        long_text = "This is a very long paragraph that has many words in it and should be translated fully."
        seg = _make_segment("s1", long_text)
        ts = self._ts(seg, "Hi")
        issues = check_batch_quality([seg], [ts], "en", "fr")
        names = [i.check_name for i in issues]
        assert "short_translation" in names

    def test_hallucinated_paragraph_detected(self):
        seg = _make_segment("s1", "Hello")
        ts = self._ts(seg, "H" * 500)
        issues = check_batch_quality([seg], [ts], "en", "fr")
        names = [i.check_name for i in issues]
        assert "hallucinated_paragraph" in names

    def test_short_check_skipped_for_short_originals(self):
        seg = _make_segment("s1", "Hi")
        ts = self._ts(seg, "B")
        issues = check_batch_quality([seg], [ts], "en", "fr")
        # Original is only 2 chars, below the 20-char threshold
        assert not any(i.check_name == "short_translation" for i in issues)

    def test_quality_issues_do_not_raise_exceptions(self):
        seg = _make_segment("s1", "Bonjour le monde")
        ts = self._ts(seg, "Bonjour le monde")
        issues = check_batch_quality([seg], [ts], "fr", "en")
        assert isinstance(issues, list)


# ── Prompt loader tests ────────────────────────────────────────────────────


class TestPromptLoader:

    def test_load_translate_prompt(self, tmp_path):
        from app.pipeline.translation.prompt_loader import clear_cache, load_prompt

        clear_cache()
        prompt_dir = tmp_path / "translation"
        prompt_dir.mkdir()
        (prompt_dir / "test_prompt.yaml").write_text(
            "prompt_id: test-v1\n"
            "prompt_version: '1.0'\n"
            "target_stage: translation\n"
            "model_family_compatibility: claude\n"
            "system: You are a translator.\n"
            "user_template: Translate {segments_json} from {source_language} to {target_language}.\n"
        )

        tmpl = load_prompt("translation/test_prompt.yaml", prompts_root=str(tmp_path))
        assert tmpl.prompt_id == "test-v1"
        assert tmpl.prompt_version == "1.0"
        assert "translator" in tmpl.system

    def test_render_user_template(self, tmp_path):
        from app.pipeline.translation.prompt_loader import clear_cache, load_prompt

        clear_cache()
        d = tmp_path / "tr"
        d.mkdir()
        (d / "t.yaml").write_text(
            "prompt_id: t\n"
            "prompt_version: '1'\n"
            "target_stage: t\n"
            "model_family_compatibility: c\n"
            "system: sys\n"
            "user_template: '{source_language} -> {target_language}'\n"
        )
        tmpl = load_prompt("tr/t.yaml", prompts_root=str(tmp_path))
        rendered = tmpl.render_user(source_language="fr", target_language="en")
        assert rendered == "fr -> en"

    def test_missing_prompt_raises_file_not_found(self, tmp_path):
        from app.pipeline.translation.prompt_loader import clear_cache, load_prompt

        clear_cache()
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent/prompt.yaml", prompts_root=str(tmp_path))

    def test_missing_field_raises_value_error(self, tmp_path):
        from app.pipeline.translation.prompt_loader import clear_cache, load_prompt

        clear_cache()
        d = tmp_path / "tr"
        d.mkdir()
        (d / "bad.yaml").write_text("prompt_id: only-id\n")
        with pytest.raises(ValueError, match="missing required fields"):
            load_prompt("tr/bad.yaml", prompts_root=str(tmp_path))


# ── AnthropicProvider caching tests ───────────────────────────────────────


class TestAnthropicProviderCaching:
    """Unit tests for prompt caching behaviour in AnthropicProvider._call_api."""

    def _make_provider(self):
        from app.pipeline.translation.provider import AnthropicProvider
        return AnthropicProvider(model="claude-test")

    def _make_usage(self, input_tokens=100, output_tokens=50,
                    cache_creation=None, cache_read=None):
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        if cache_creation is not None:
            usage.cache_creation_input_tokens = cache_creation
        else:
            del usage.cache_creation_input_tokens
        if cache_read is not None:
            usage.cache_read_input_tokens = cache_read
        else:
            del usage.cache_read_input_tokens
        return usage

    def _make_response(self, usage):
        response = MagicMock()
        response.content = [MagicMock(text='{"translations": []}')]
        response.usage = usage
        return response

    def test_system_prompt_sent_with_cache_control(self):
        provider = self._make_provider()
        usage = self._make_usage(cache_creation=0, cache_read=0)
        response = self._make_response(usage)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            mock_get_client.return_value = mock_client

            provider._call_api(system="You are a translator.", user="Translate this.")

        call_kwargs = mock_client.messages.create.call_args[1]
        system_arg = call_kwargs["system"]
        assert isinstance(system_arg, list)
        assert len(system_arg) == 1
        block = system_arg[0]
        assert block["type"] == "text"
        assert block["text"] == "You are a translator."
        assert block["cache_control"] == {"type": "ephemeral"}

    def test_cache_creation_tokens_flow_through(self):
        provider = self._make_provider()
        usage = self._make_usage(input_tokens=100, output_tokens=50,
                                 cache_creation=512, cache_read=0)
        response = self._make_response(usage)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            mock_get_client.return_value = mock_client

            result = provider._call_api(system="sys", user="user")

        _text, _tokens_in, _tokens_out, cache_creation, cache_read, _latency = result
        assert cache_creation == 512
        assert cache_read == 0

    def test_cache_read_tokens_flow_through(self):
        provider = self._make_provider()
        usage = self._make_usage(input_tokens=100, output_tokens=50,
                                 cache_creation=0, cache_read=2048)
        response = self._make_response(usage)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            mock_get_client.return_value = mock_client

            result = provider._call_api(system="sys", user="user")

        _text, _tokens_in, _tokens_out, cache_creation, cache_read, _latency = result
        assert cache_creation == 0
        assert cache_read == 2048

    def test_cache_tokens_absent_from_usage_safe(self):
        provider = self._make_provider()
        # usage object has no cache_creation_input_tokens or cache_read_input_tokens
        usage = self._make_usage(input_tokens=100, output_tokens=50,
                                 cache_creation=None, cache_read=None)
        response = self._make_response(usage)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            mock_get_client.return_value = mock_client

            result = provider._call_api(system="sys", user="user")

        _text, _tokens_in, _tokens_out, cache_creation, cache_read, _latency = result
        assert cache_creation == 0
        assert cache_read == 0


# ── AnthropicProvider parse response tests ────────────────────────────────


class TestAnthropicProviderParseResponse:
    """Unit tests for AnthropicProvider._parse_response with compact JSON."""

    def _make_provider(self):
        from app.pipeline.translation.provider import AnthropicProvider
        return AnthropicProvider(model="claude-test")

    def test_parse_response_handles_compact_json(self):
        provider = self._make_provider()
        compact = '{"translations":[{"id":"s1","translation":"Hello"}]}'
        result = provider._parse_response(compact)
        assert isinstance(result, dict)
        assert "translations" in result
        assert result["translations"][0]["id"] == "s1"
        assert result["translations"][0]["translation"] == "Hello"

    def test_parse_response_handles_compact_json_with_fence(self):
        provider = self._make_provider()
        compact = '{"translations":[{"id":"s1","translation":"Hello"}]}'
        fenced = f"```json\n{compact}\n```"
        result = provider._parse_response(fenced)
        assert isinstance(result, dict)
        assert "translations" in result
        assert result["translations"][0]["id"] == "s1"
        assert result["translations"][0]["translation"] == "Hello"


# ── ProviderBillingError classification tests ─────────────────────────────────


class TestProviderBillingErrorClassification:
    """Verify billing-related 400 errors are raised as ProviderBillingError
    and classified as 'system' rather than 'content-deterministic'."""

    def _make_provider(self):
        from app.pipeline.translation.provider import AnthropicProvider
        return AnthropicProvider(model="claude-test")

    def _make_api_status_error(self, status_code: int, message: str):
        import anthropic
        response = MagicMock()
        response.status_code = status_code
        err = anthropic.APIStatusError(message, response=response, body={})
        return err

    def test_billing_400_raises_provider_billing_error(self):
        from app.pipeline.translation.models import ProviderBillingError
        from app.pipeline.translation.provider import AnthropicProvider
        provider = self._make_provider()
        billing_exc = self._make_api_status_error(
            400,
            "Your credit balance is too low to access the Anthropic API."
        )
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = billing_exc
            mock_get_client.return_value = mock_client
            with pytest.raises(ProviderBillingError):
                provider._call_api(system="sys", user="user")

    def test_non_billing_400_raises_content_deterministic_error(self):
        from app.pipeline.translation.provider import AnthropicProvider
        provider = self._make_provider()
        other_exc = self._make_api_status_error(
            400,
            "invalid_request_error: bad prompt format"
        )
        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = other_exc
            mock_get_client.return_value = mock_client
            with pytest.raises(ContentDeterministicError):
                provider._call_api(system="sys", user="user")

    def test_billing_error_classified_as_system(self):
        from app.pipeline.translation.models import ProviderBillingError
        from app.worker.orchestrator import _classify_failure
        exc = ProviderBillingError("credit balance is too low")
        assert _classify_failure(exc) == "system"

    def test_content_deterministic_error_classification_unchanged(self):
        from app.worker.orchestrator import _classify_failure
        exc = ContentDeterministicError("bad json")
        assert _classify_failure(exc) == "content-deterministic"
