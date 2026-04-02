"""Unit tests for the EPUB upload validator (app/upload/validator.py).

All tests use in-memory bytes — no I/O, no DB, no storage.
"""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from app.upload.validator import (
    MAX_ENTRY_COUNT,
    MAX_EXPANSION_RATIO,
    MAX_FILE_SIZE_BYTES,
    MAX_HTML_FILES,
    MAX_SPINE_ITEMS,
    UploadValidationError,
    ValidationResult,
    validate_epub_bytes,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_epub(
    *,
    with_mimetype: bool = True,
    with_drm: bool = False,
    extra_entries: int = 0,
    spine_items: int = 1,
    html_files: int = 1,
    opf_spine_xml: str | None = None,
) -> bytes:
    """Build a minimal syntactically valid EPUB3 in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        if with_mimetype:
            zf.writestr("mimetype", "application/epub+zip")

        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0"'
            ' xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf"'
            ' media-type="application/oebps-package+xml"/>'
            "</rootfiles>"
            "</container>",
        )

        if with_drm:
            zf.writestr("META-INF/encryption.xml", "<encryption/>")

        # OPF file
        if opf_spine_xml is None:
            itemrefs = "".join(
                f'<itemref idref="ch{i}"/>' for i in range(spine_items)
            )
            items = "".join(
                f'<item id="ch{i}" href="ch{i}.xhtml"'
                ' media-type="application/xhtml+xml"/>'
                for i in range(spine_items)
            )
            opf_spine_xml = (
                '<?xml version="1.0"?>'
                '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                "<dc:title>Test</dc:title>"
                "</metadata>"
                f"<manifest>{items}</manifest>"
                f"<spine>{itemrefs}</spine>"
                "</package>"
            )
        zf.writestr("OEBPS/content.opf", opf_spine_xml)

        for i in range(html_files):
            zf.writestr(f"OEBPS/ch{i}.xhtml", f"<html><body><p>Chapter {i}</p></body></html>")

        for i in range(extra_entries):
            zf.writestr(f"extra/file_{i}.bin", b"x" * 10)

    return buf.getvalue()


# ── Happy path ────────────────────────────────────────────────────────────────

def test_valid_epub_returns_result() -> None:
    data = _make_epub()
    result = validate_epub_bytes(data)
    assert isinstance(result, ValidationResult)
    assert result.content_sha256 == hashlib.sha256(data).hexdigest()
    assert result.mime_type == "application/epub+zip"


def test_valid_epub_without_mimetype_file_passes() -> None:
    """mimetype file is optional — not all EPUBs include it."""
    data = _make_epub(with_mimetype=False)
    result = validate_epub_bytes(data)
    assert result.content_sha256 == hashlib.sha256(data).hexdigest()


# ── File size ─────────────────────────────────────────────────────────────────

def test_file_too_large_raises() -> None:
    oversized = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(oversized)
    assert exc_info.value.code == "file_too_large"


# ── ZIP integrity ─────────────────────────────────────────────────────────────

def test_not_a_zip_raises() -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(b"this is not a zip file at all")
    assert exc_info.value.code == "invalid_epub"


def test_empty_bytes_raises() -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(b"")
    assert exc_info.value.code == "file_too_large" or exc_info.value.code == "invalid_epub"


# ── DRM ───────────────────────────────────────────────────────────────────────

def test_drm_epub_raises() -> None:
    data = _make_epub(with_drm=True)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(data)
    assert exc_info.value.code == "drm_detected"


# ── Entry count ───────────────────────────────────────────────────────────────

def test_too_many_entries_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.upload.validator as v
    monkeypatch.setattr(v, "MAX_ENTRY_COUNT", 3)
    data = _make_epub(extra_entries=10)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(data)
    assert exc_info.value.code == "too_many_entries"


# ── Zip bomb ──────────────────────────────────────────────────────────────────

def test_zip_bomb_expansion_ratio_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Create a ZIP where uncompressed/compressed ratio exceeds limit."""
    import app.upload.validator as v
    monkeypatch.setattr(v, "MAX_EXPANSION_RATIO", 2)
    # Create a file with high compression ratio (repeated bytes compress well)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container/>")
        # 1 MB of zeros compresses to ~1 KB — ratio ~1000:1
        zf.writestr("big_file.bin", b"\x00" * (1024 * 1024))
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(buf.getvalue())
    assert exc_info.value.code == "zip_bomb_detected"


def test_uncompressed_size_limit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.upload.validator as v
    monkeypatch.setattr(v, "MAX_UNCOMPRESSED_BYTES", 100)
    data = _make_epub()
    # Make it report huge uncompressed size by monkeypatching — instead simulate
    # via a real archive with content larger than our patched limit
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<c/>")
        # 200 bytes uncompressed, limit is 100
        zf.writestr("large.bin", b"x" * 200)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(buf.getvalue())
    assert exc_info.value.code == "archive_too_large"


# ── HTML file count ───────────────────────────────────────────────────────────

def test_too_many_html_files_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.upload.validator as v
    monkeypatch.setattr(v, "MAX_HTML_FILES", 2)
    data = _make_epub(html_files=5)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(data)
    assert exc_info.value.code == "too_many_html_files"


# ── MIME type ─────────────────────────────────────────────────────────────────

def test_wrong_mime_type_raises() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("mimetype", "application/pdf")
        zf.writestr("META-INF/container.xml", "<container/>")
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(buf.getvalue())
    assert exc_info.value.code == "invalid_mime_type"


# ── Spine item count ──────────────────────────────────────────────────────────

def test_too_many_spine_items_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.upload.validator as v
    monkeypatch.setattr(v, "MAX_SPINE_ITEMS", 2)
    data = _make_epub(spine_items=5, html_files=5)
    with pytest.raises(UploadValidationError) as exc_info:
        validate_epub_bytes(data)
    assert exc_info.value.code == "too_many_chapters"


def test_spine_parse_failure_is_skipped() -> None:
    """If container.xml or OPF is malformed, spine check is skipped (not rejected)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "NOT XML")
        zf.writestr("OEBPS/chapter1.xhtml", "<html/>")
    result = validate_epub_bytes(buf.getvalue())
    assert result.mime_type == "application/epub+zip"
