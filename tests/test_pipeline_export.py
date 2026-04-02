"""Tests for the FEAT-EXPORT pipeline stage.

Covers:
- ExportConfig and ExportedEpub models
- export_document() stage function
- epub_builder.build_epub() with Translate and Guided modes
- Sub-segment content in output chapters
- Disclaimer page presence
- Metadata injection (title suffix, language, description)
- SHA-256 fingerprint consistency
- Storage client put_object_bytes
- Error cases (empty blocks, unsupported mode)
"""
from __future__ import annotations

import hashlib
import io
import uuid
from typing import List

import pytest


# ── Test EPUB builder (a minimal source EPUB) ─────────────────────────────

def _make_minimal_epub(title: str = "Test Book", author: str = "Author X") -> bytes:
    """Produce a minimal valid EPUB using ebooklib."""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("test-id-001")
    book.set_title(title)
    book.set_language("it")
    book.add_author(author)

    c1 = epub.EpubHtml(uid="chapter1", file_name="chap1.xhtml", lang="it")
    c1.set_content(
        b"<?xml version='1.0' encoding='utf-8'?>"
        b"<html xmlns='http://www.w3.org/1999/xhtml'>"
        b"<head><title>Chapter 1</title></head>"
        b"<body><p>Capitolo uno.</p></body></html>"
    )
    book.add_item(c1)

    c2 = epub.EpubHtml(uid="chapter2", file_name="chap2.xhtml", lang="it")
    c2.set_content(
        b"<?xml version='1.0' encoding='utf-8'?>"
        b"<html xmlns='http://www.w3.org/1999/xhtml'>"
        b"<head><title>Chapter 2</title></head>"
        b"<body><p>Capitolo due.</p></body></html>"
    )
    book.add_item(c2)

    nav = epub.EpubNcx()
    nav2 = epub.EpubNav()
    book.add_item(nav)
    book.add_item(nav2)
    book.spine = ["nav", c1, c2]

    buf = io.BytesIO()
    epub.write_epub(buf, book, {})
    return buf.getvalue()


def _make_formatted_document(mode: str, chapter_ids: List[str]) -> object:
    """Build a FormattedDocument with one block per chapter."""
    from app.pipeline.formatting.models import FormattedBlock, FormattedDocument

    blocks = []
    for i, cid in enumerate(chapter_ids):
        if mode == "guided":
            block = FormattedBlock(
                paragraph_id=f"para-{i}",
                chapter_ref=cid,
                original=f"Testo originale {i}.",
                translation=f"Original text {i}.",
                explanations=[f"Note {i}: vocab explanation"],
                original_repeat=f"Testo originale {i}.",
            )
        else:
            block = FormattedBlock(
                paragraph_id=f"para-{i}",
                chapter_ref=cid,
                original=f"Testo originale {i}.",
                translation=f"Original text {i}.",
                explanations=[],
                original_repeat=None,
            )
        blocks.append(block)

    return FormattedDocument(
        document_id=uuid.uuid4(),
        mode=mode,
        formatted_blocks=blocks,
    )


def _make_export_config(mode: str = "translate") -> object:
    from app.pipeline.export.models import ExportConfig

    return ExportConfig(
        mode=mode,
        target_language="en",
        source_title="Test Book",
        source_author="Author X",
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
    )



# ── Model tests ───────────────────────────────────────────────────────────

class TestExportModels:
    def test_export_config_is_frozen(self):
        from app.pipeline.export.models import ExportConfig

        cfg = ExportConfig(
            mode="translate",
            target_language="en",
            source_title="Book",
            source_author="Author",
            user_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
        )
        with pytest.raises((AttributeError, TypeError)):
            cfg.mode = "guided"  # type: ignore[misc]

    def test_exported_epub_is_frozen(self):
        from app.pipeline.export.models import ExportedEpub

        ep = ExportedEpub(epub_bytes=b"x", sha256_fingerprint="abc", size_bytes=1)
        with pytest.raises((AttributeError, TypeError)):
            ep.size_bytes = 99  # type: ignore[misc]

    def test_exported_epub_size_bytes_matches(self):
        from app.pipeline.export.models import ExportedEpub

        data = b"hello epub"
        ep = ExportedEpub(epub_bytes=data, sha256_fingerprint="x", size_bytes=len(data))
        assert ep.size_bytes == 10

    def test_export_error_is_exception(self):
        from app.pipeline.export.models import ExportError

        err = ExportError("bad")
        assert isinstance(err, Exception)


# ── epub_builder tests ────────────────────────────────────────────────────

class TestEpubBuilder:
    def setup_method(self):
        from ebooklib import epub

        self.epub = epub
        self.source_bytes = _make_minimal_epub("Test Book", "Author X")

    def _get_chapter_ids(self) -> List[str]:
        """Return the ids of ITEM_DOCUMENT items in the source EPUB."""
        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(io.BytesIO(self.source_bytes), options={"ignore_ncx": False})
        return [
            item.id
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if not item.id.startswith("nav")
        ]

    def test_build_epub_returns_bytes(self):
        from app.pipeline.export.epub_builder import build_epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result = build_epub(formatted, self.source_bytes, config)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_epub_is_valid_epub(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        # Must be parseable by ebooklib
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        assert book is not None

    def test_metadata_title_updated(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        titles = book.get_metadata("DC", "title")
        assert len(titles) >= 1
        title_val = titles[0][0]
        assert "— Translate, EN" in title_val
        assert "Test Book" in title_val

    def test_metadata_language_updated(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        langs = book.get_metadata("DC", "language")
        assert any(lng[0] == "en" for lng in langs)

    def test_metadata_description_injected(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        descs = book.get_metadata("DC", "description")
        assert len(descs) >= 1
        assert "Unfolda" in descs[0][0]

    def test_disclaimer_page_present_in_spine(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        spine_ids = [item_id for item_id, _ in book.spine]
        disclaimer_items = [
            iid for iid in spine_ids
            if "disclaimer" in str(iid).lower() or "unfolda" in str(iid).lower()
        ]
        assert len(disclaimer_items) >= 1

    def test_translate_mode_no_original_in_blocks(self):
        from app.pipeline.export.epub_builder import build_epub
        import ebooklib
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        content_found = False
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            raw = item.get_content().decode("utf-8", errors="ignore")
            if "Original text" in raw:
                content_found = True
                assert 'class="original"' not in raw, "Translate mode must not render original class"
        assert content_found, "Expected translated content in at least one chapter item"

    def test_guided_mode_contains_original_and_translation(self):
        from app.pipeline.export.epub_builder import build_epub
        import ebooklib
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("guided", chapter_ids)
        config = _make_export_config("guided")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        found_original = False
        found_translation = False
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            raw = item.get_content().decode("utf-8", errors="ignore")
            if 'class="original"' in raw:
                found_original = True
            if 'class="translation"' in raw:
                found_translation = True
        assert found_original
        assert found_translation

    def test_guided_mode_contains_explanations(self):
        from app.pipeline.export.epub_builder import build_epub
        import ebooklib
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("guided", chapter_ids)
        config = _make_export_config("guided")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        found_expl = False
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            raw = item.get_content().decode("utf-8", errors="ignore")
            if 'class="explanation"' in raw:
                found_expl = True
        assert found_expl

    def test_guided_mode_title_suffix(self):
        from app.pipeline.export.epub_builder import build_epub
        from ebooklib import epub

        chapter_ids = self._get_chapter_ids()
        formatted = _make_formatted_document("guided", chapter_ids)
        config = _make_export_config("guided")
        result_bytes = build_epub(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
        titles = book.get_metadata("DC", "title")
        assert "— Guided, EN" in titles[0][0]

    def test_invalid_source_bytes_raises_export_error(self):
        from app.pipeline.export.epub_builder import build_epub
        from app.pipeline.export.models import ExportError

        chapter_ids = ["chapter1"]
        formatted = _make_formatted_document("translate", chapter_ids)
        config = _make_export_config("translate")
        with pytest.raises(ExportError):
            build_epub(formatted, b"not an epub", config)

    def test_chapters_without_blocks_left_unchanged(self):
        """Chapters with no matching blocks should keep their original content."""
        from app.pipeline.export.epub_builder import build_epub
        import ebooklib
        from ebooklib import epub

        # Only map blocks to chapter1, leave chapter2 unmapped
        chapter_ids = self._get_chapter_ids()
        if len(chapter_ids) >= 2:
            formatted = _make_formatted_document("translate", [chapter_ids[0]])
            config = _make_export_config("translate")
            result_bytes = build_epub(formatted, self.source_bytes, config)
            book = epub.read_epub(io.BytesIO(result_bytes), options={"ignore_ncx": False})
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                if item.id == chapter_ids[1]:
                    raw = item.get_content().decode("utf-8", errors="ignore")
                    assert "Capitolo due" in raw



# ── stage.export_document tests ───────────────────────────────────────────

class TestExportDocumentStage:
    def setup_method(self):
        self.source_bytes = _make_minimal_epub("Book", "Writer")
        self._book_chapter_ids = self._get_chapter_ids()

    def _get_chapter_ids(self) -> List[str]:
        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(
            io.BytesIO(_make_minimal_epub("Book", "Writer")),
            options={"ignore_ncx": False},
        )
        return [
            item.id
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if not item.id.startswith("nav")
        ]

    def test_returns_exported_epub(self):
        from app.pipeline.export.stage import export_document
        from app.pipeline.export.models import ExportedEpub

        formatted = _make_formatted_document("translate", self._book_chapter_ids)
        config = _make_export_config("translate")
        result = export_document(formatted, self.source_bytes, config)
        assert isinstance(result, ExportedEpub)

    def test_sha256_fingerprint_is_correct(self):
        from app.pipeline.export.stage import export_document

        formatted = _make_formatted_document("translate", self._book_chapter_ids)
        config = _make_export_config("translate")
        result = export_document(formatted, self.source_bytes, config)
        expected = hashlib.sha256(result.epub_bytes).hexdigest()
        assert result.sha256_fingerprint == expected

    def test_size_bytes_is_correct(self):
        from app.pipeline.export.stage import export_document

        formatted = _make_formatted_document("translate", self._book_chapter_ids)
        config = _make_export_config("translate")
        result = export_document(formatted, self.source_bytes, config)
        assert result.size_bytes == len(result.epub_bytes)

        from app.pipeline.export.stage import export_document
        from app.pipeline.export.models import ExportError
        from app.pipeline.formatting.models import FormattedDocument

        empty = FormattedDocument(
            document_id=uuid.uuid4(),
            mode="translate",
            formatted_blocks=[],
        )
        config = _make_export_config("translate")
        with pytest.raises(ExportError):
            export_document(empty, self.source_bytes, config)

    def test_unsupported_mode_raises_export_error(self):
        from app.pipeline.export.stage import export_document
        from app.pipeline.export.models import ExportConfig, ExportError
        from app.pipeline.formatting.models import FormattedBlock, FormattedDocument

        block = FormattedBlock(
            paragraph_id="p1",
            chapter_ref="chap1",
            original="x",
            translation="x",
            explanations=[],
            original_repeat=None,
        )
        doc = FormattedDocument(
            document_id=uuid.uuid4(),
            mode="unknown_mode",
            formatted_blocks=[block],
        )
        config = ExportConfig(
            mode="unknown_mode",
            target_language="en",
            source_title="T",
            source_author="A",
            user_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
        )
        with pytest.raises(ExportError):
            export_document(doc, self.source_bytes, config)

    def test_empty_source_bytes_raises_export_error(self):
        from app.pipeline.export.stage import export_document
        from app.pipeline.export.models import ExportError

        formatted = _make_formatted_document("translate", self._book_chapter_ids)
        config = _make_export_config("translate")
        with pytest.raises(ExportError):
            export_document(formatted, b"", config)

    def test_guided_mode_produces_valid_epub(self):
        from app.pipeline.export.stage import export_document
        from ebooklib import epub

        formatted = _make_formatted_document("guided", self._book_chapter_ids)
        config = _make_export_config("guided")
        result = export_document(formatted, self.source_bytes, config)
        book = epub.read_epub(io.BytesIO(result.epub_bytes), options={"ignore_ncx": False})
        assert book is not None


# ── Storage put_object_bytes tests ───────────────────────────────────────

class TestStoragePutObjectBytes:
    def test_fake_storage_put_and_get(self):
        from app.storage.client import FakeStorageClient

        client = FakeStorageClient()
        client.put_object_bytes("users/1/jobs/2/output_epub/3", b"epub data")
        result = client.get_object_bytes("users/1/jobs/2/output_epub/3")
        assert result == b"epub data"

    def test_fake_storage_overwrites_existing(self):
        from app.storage.client import FakeStorageClient

        client = FakeStorageClient()
        client.put_object_bytes("key", b"v1")
        client.put_object_bytes("key", b"v2")
        assert client.get_object_bytes("key") == b"v2"

    def test_protocol_has_put_object_bytes(self):
        from app.storage.client import StorageClientProtocol, FakeStorageClient

        client = FakeStorageClient()
        assert isinstance(client, StorageClientProtocol)
        assert hasattr(client, "put_object_bytes")


# ── HTML escaping / safety tests ─────────────────────────────────────────

class TestHtmlEscaping:
    def test_xss_in_translation_is_escaped(self):
        from app.pipeline.export.epub_builder import _build_block_html
        from app.pipeline.formatting.models import FormattedBlock

        block = FormattedBlock(
            paragraph_id="p1",
            chapter_ref="c1",
            original="<script>alert(1)</script>",
            translation="<b>bold</b>",
            explanations=["<em>note</em>"],
            original_repeat="<script>alert(1)</script>",
        )
        html_output = _build_block_html(block, "guided")
        assert "<script>" not in html_output
        assert "&lt;script&gt;" in html_output

    def test_xss_in_explanation_is_escaped(self):
        from app.pipeline.export.epub_builder import _build_block_html
        from app.pipeline.formatting.models import FormattedBlock

        block = FormattedBlock(
            paragraph_id="p1",
            chapter_ref="c1",
            original="text",
            translation="text",
            explanations=["<script>evil()</script>"],
            original_repeat="text",
        )
        html_output = _build_block_html(block, "guided")
        assert "<script>" not in html_output


