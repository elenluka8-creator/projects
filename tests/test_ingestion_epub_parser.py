"""Tests for the EPUB parser.

Uses minimal synthetic EPUB zip structures to avoid requiring real EPUB files.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.pipeline.ingestion.epub_parser import ParsedEpub, parse
from app.pipeline.ingestion.models import DrmDetectedError, EpubParseError


def _make_minimal_epub(
    title: str = "Test Book",
    author: str = "Test Author",
    chapters: list[str] | None = None,
    include_drm: bool = False,
    include_image: bool = False,
    include_stylesheet: bool = False,
    bad_zip: bool = False,
) -> bytes:
    """Build a minimal valid EPUB 2.0 zip in memory for testing."""
    if bad_zip:
        return b"this is not a zip file at all"

    chapters = chapters or ["Hello world. This is chapter one."]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")

        container_xml = (
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "  <rootfiles>"
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "  </rootfiles>"
            "</container>"
        )
        zf.writestr("META-INF/container.xml", container_xml)

        if include_drm:
            zf.writestr("META-INF/encryption.xml", "<encryption/>")

        spine_items = ""
        manifest_items = ""
        for i, chapter_text in enumerate(chapters):
            item_id = f"ch{i}"
            filename = f"OEBPS/chapter{i}.xhtml"
            html = (
                "<?xml version='1.0' encoding='utf-8'?>"
                '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
                '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>Chapter {i}</title></head>"
                f"<body><h1>Chapter {i + 1}</h1><p>{chapter_text}</p></body>"
                "</html>"
            )
            zf.writestr(filename, html)
            manifest_items += (
                f'<item id="{item_id}" href="chapter{i}.xhtml" '
                f'media-type="application/xhtml+xml"/>\n'
            )
            spine_items += f'<itemref idref="{item_id}"/>\n'

        if include_image:
            zf.writestr("OEBPS/images/cover.png", b"\x89PNG\r\n")
            manifest_items += (
                '<item id="cover-img" href="images/cover.png" media-type="image/png"/>\n'
            )

        if include_stylesheet:
            zf.writestr("OEBPS/styles/main.css", "body { font-family: serif; }")
            manifest_items += (
                '<item id="css" href="styles/main.css" media-type="text/css"/>\n'
            )

        opf = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">'
            "  <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            f"    <dc:title>{title}</dc:title>"
            f"    <dc:creator>{author}</dc:creator>"
            "    <dc:language>en</dc:language>"
            '    <dc:identifier id="uid">test-book-001</dc:identifier>'
            "  </metadata>"
            f"  <manifest>{manifest_items}</manifest>"
            f"  <spine>{spine_items}</spine>"
            "</package>"
        )
        zf.writestr("OEBPS/content.opf", opf)

    return buf.getvalue()


class TestDrmDetection:
    def test_drm_epub_raises_drm_error(self):
        epub = _make_minimal_epub(include_drm=True)
        with pytest.raises(DrmDetectedError) as exc_info:
            parse(epub)
        assert "encryption.xml" in str(exc_info.value).lower() or "drm" in str(exc_info.value).lower()

    def test_clean_epub_does_not_raise_drm(self):
        epub = _make_minimal_epub()
        result = parse(epub)
        assert isinstance(result, ParsedEpub)


class TestEpubParsing:
    def test_title_extracted(self):
        epub = _make_minimal_epub(title="My Great Novel")
        result = parse(epub)
        assert result.title == "My Great Novel"

    def test_author_extracted(self):
        epub = _make_minimal_epub(author="Jane Doe")
        result = parse(epub)
        assert result.author == "Jane Doe"

    def test_text_extracted(self):
        epub = _make_minimal_epub(chapters=["The quick brown fox."])
        result = parse(epub)
        assert "quick brown fox" in result.text

    def test_word_count_positive(self):
        epub = _make_minimal_epub(chapters=["One two three four five."])
        result = parse(epub)
        assert result.source_word_count > 0

    def test_chapter_refs_populated(self):
        epub = _make_minimal_epub(chapters=["Chapter one text.", "Chapter two text."])
        result = parse(epub)
        assert len(result.chapter_refs) == 2
        assert result.chapter_refs[0].order == 0
        assert result.chapter_refs[1].order == 1

    def test_chapter_ref_ids_are_strings(self):
        epub = _make_minimal_epub(chapters=["text"])
        result = parse(epub)
        assert all(isinstance(c.chapter_id, str) for c in result.chapter_refs)

    def test_image_produces_structural_ref(self):
        epub = _make_minimal_epub(include_image=True)
        result = parse(epub)
        image_refs = [r for r in result.structural_refs if r.ref_type == "image"]
        assert len(image_refs) >= 1

    def test_stylesheet_produces_structural_ref(self):
        epub = _make_minimal_epub(include_stylesheet=True)
        result = parse(epub)
        css_refs = [r for r in result.structural_refs if r.ref_type == "stylesheet"]
        assert len(css_refs) >= 1

    def test_metadata_contains_language(self):
        epub = _make_minimal_epub()
        result = parse(epub)
        assert "epub_language" in result.metadata
        assert result.metadata["epub_language"] == "en"


class TestInvalidInput:
    def test_bad_zip_raises_parse_error(self):
        with pytest.raises(EpubParseError):
            parse(_make_minimal_epub(bad_zip=True))

    def test_empty_bytes_raises_parse_error(self):
        with pytest.raises(EpubParseError):
            parse(b"")
