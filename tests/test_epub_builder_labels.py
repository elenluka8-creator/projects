"""Unit tests for localized block labels and disclaimer text in epub_builder.

These tests exercise only the pure helper functions and HTML-generation logic —
no real EPUB I/O, no ebooklib dependency.
"""
from __future__ import annotations

import pytest

from app.pipeline.export.epub_builder import (
    _get_block_labels,
    _get_disclaimer_text,
    _build_block_html,
    _build_chapter_body,
    _build_disclaimer_item,
    _BLOCK_LABELS,
    _DISCLAIMER_TEXTS,
)
from app.pipeline.export.models import ExportConfig
from app.pipeline.formatting.models import FormattedBlock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(target_language: str = "en", mode: str = "guided") -> ExportConfig:
    import uuid
    return ExportConfig(
        mode=mode,
        target_language=target_language,
        source_title="Test Book",
        source_author="Test Author",
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
    )


def _make_block(*, with_notes: bool = False) -> FormattedBlock:
    return FormattedBlock(
        paragraph_id="p1",
        chapter_ref="ch1",
        original="Hello world.",
        translation="Привет мир.",
        original_repeat="Hello world.",
        explanations=["A greeting."] if with_notes else [],
    )


# ── _get_block_labels ─────────────────────────────────────────────────────────

def test_block_labels_en() -> None:
    labels = _get_block_labels("en")
    assert labels["original"] == "Original"
    assert labels["translation"] == "Translation"
    assert labels["notes"] == "Notes"
    assert labels["original_repeat"] == "Original (repeat)"


def test_block_labels_ru() -> None:
    labels = _get_block_labels("ru")
    assert labels["original"] == "Оригинал"
    assert labels["translation"] == "Перевод"
    assert labels["notes"] == "Примечания"
    assert labels["original_repeat"] == "Оригинал (повтор)"


def test_block_labels_sr() -> None:
    labels = _get_block_labels("sr")
    assert labels["original"] == "Original"
    assert labels["translation"] == "Prevod"
    assert labels["notes"] == "Napomene"
    assert labels["original_repeat"] == "Original (ponavljanje)"


def test_block_labels_unknown_falls_back_to_en() -> None:
    labels = _get_block_labels("xx")
    assert labels == _BLOCK_LABELS["en"]


# ── _get_disclaimer_text ──────────────────────────────────────────────────────

def test_disclaimer_text_ru_contains_cyrillic() -> None:
    d = _get_disclaimer_text("ru")
    assert "Уведомление" in d["heading"]
    assert "Режим" in d["mode_label"]
    assert "Целевой язык" in d["lang_label"]
    assert "личного изучения языка" in d["footer"]


def test_disclaimer_text_sr() -> None:
    d = _get_disclaimer_text("sr")
    assert "Obaveštenje" in d["heading"]
    assert "Način" in d["mode_label"]
    assert "Ciljni jezik" in d["lang_label"]
    assert "učenje jezika" in d["footer"]


def test_disclaimer_text_unknown_falls_back_to_en() -> None:
    d = _get_disclaimer_text("zz")
    assert d == _DISCLAIMER_TEXTS["en"]


# ── _build_block_html ─────────────────────────────────────────────────────────

def test_guided_block_uses_ru_labels() -> None:
    block = _make_block()
    labels = _get_block_labels("ru")
    html = _build_block_html(block, "guided", labels)
    assert "Оригинал" in html
    assert "Перевод" in html
    assert "Оригинал (повтор)" in html
    assert "Original" not in html  # English label must not appear
    assert "Translation" not in html


def test_guided_block_with_notes_uses_ru_notes_label() -> None:
    block = _make_block(with_notes=True)
    labels = _get_block_labels("ru")
    html = _build_block_html(block, "guided", labels)
    assert "Примечания" in html
    assert "Notes" not in html


def test_guided_block_sr_labels() -> None:
    block = _make_block()
    labels = _get_block_labels("sr")
    html = _build_block_html(block, "guided", labels)
    assert "Prevod" in html
    assert "Original (ponavljanje)" in html


def test_translate_mode_has_no_labels() -> None:
    block = _make_block()
    labels = _get_block_labels("ru")
    html = _build_block_html(block, "translate", labels)
    assert "block-label" not in html
    assert "Оригинал" not in html
    assert "translation" in html  # CSS class is always English


# ── _build_chapter_body ───────────────────────────────────────────────────────

def test_chapter_body_ru_guided() -> None:
    blocks = [_make_block(), _make_block()]
    body = _build_chapter_body(blocks, mode="guided", target_language="ru")
    assert "Оригинал" in body
    assert "Перевод" in body
    assert "unfolda-hr" in body  # separator between blocks


def test_chapter_body_en_guided_default() -> None:
    blocks = [_make_block()]
    body = _build_chapter_body(blocks, mode="guided")
    assert "Original" in body
    assert "Translation" in body


def test_chapter_body_translate_mode_no_labels() -> None:
    blocks = [_make_block()]
    body = _build_chapter_body(blocks, mode="translate", target_language="ru")
    assert "Оригинал" not in body
    assert "unfolda-hr" not in body


# ── _build_disclaimer_item ────────────────────────────────────────────────────

class _FakeEpubHtml:
    def __init__(self, *, uid, file_name, lang):
        self.uid = uid
        self.file_name = file_name
        self.lang = lang
        self._content = b""

    def set_content(self, data: bytes) -> None:
        self._content = data

    def get_content(self) -> bytes:
        return self._content


class _FakeEblib:
    EpubHtml = _FakeEpubHtml


def test_disclaimer_item_ru_is_localized() -> None:
    config = _make_config(target_language="ru")
    item = _build_disclaimer_item(config, _FakeEblib)
    content = item.get_content().decode("utf-8")
    assert "Уведомление" in content
    assert "Режим" in content
    assert "Целевой язык" in content
    assert "личного изучения" in content
    assert "AI Translation Notice" not in content


def test_disclaimer_item_sr_is_localized() -> None:
    config = _make_config(target_language="sr")
    item = _build_disclaimer_item(config, _FakeEblib)
    content = item.get_content().decode("utf-8")
    assert "Obaveštenje" in content
    assert "Način" in content
    assert "Ciljni jezik" in content


def test_disclaimer_item_en_is_english() -> None:
    config = _make_config(target_language="en")
    item = _build_disclaimer_item(config, _FakeEblib)
    content = item.get_content().decode("utf-8")
    assert "AI Translation Notice" in content
    assert "Mode" in content
    assert "Target language" in content


def test_disclaimer_item_unknown_falls_back_to_en() -> None:
    config = _make_config(target_language="fr")
    item = _build_disclaimer_item(config, _FakeEblib)
    content = item.get_content().decode("utf-8")
    assert "AI Translation Notice" in content


def test_disclaimer_item_contains_title_and_author() -> None:
    config = _make_config(target_language="ru")
    item = _build_disclaimer_item(config, _FakeEblib)
    content = item.get_content().decode("utf-8")
    assert "Test Book" in content
    assert "Test Author" in content
