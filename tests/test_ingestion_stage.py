"""Integration tests for the ingestion stage entry point.

Uses a FakeStorageClientWithBytes that stores raw bytes in memory,
so the stage can fetch the EPUB without real S3.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from typing import Dict, Optional

import pytest

from app.pipeline.ingestion.models import (
    DrmDetectedError,
    EpubParseError,
    UploadedSourceArtifact,
)
from app.pipeline.ingestion.stage import ingest


class FakeStorageClientWithBytes:
    """In-memory storage client that supports get_object_bytes for stage tests."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._store[key] = data

    def get_object_bytes(self, object_key: str) -> Optional[bytes]:
        return self._store.get(object_key)

    def get_presigned_upload_url(self, object_key: str, expires_in_seconds: int) -> str:
        return f"https://fake/upload/{object_key}"

    def get_presigned_download_url(self, object_key: str, expires_in_seconds: int) -> str:
        return f"https://fake/download/{object_key}"

    def delete_object(self, object_key: str) -> None:
        self._store.pop(object_key, None)


def _make_epub(
    title: str = "Test Book",
    author: str = "Test Author",
    chapter_text: str = "The quick brown fox jumps over the lazy dog. " * 20,
    include_drm: bool = False,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        container = (
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "  <rootfiles>"
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "  </rootfiles></container>"
        )
        zf.writestr("META-INF/container.xml", container)
        if include_drm:
            zf.writestr("META-INF/encryption.xml", "<encryption/>")
        html = (
            "<?xml version='1.0' encoding='utf-8'?>"
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            f"<head><title>Ch1</title></head><body><h1>Chapter One</h1><p>{chapter_text}</p></body>"
            "</html>"
        )
        zf.writestr("OEBPS/chapter0.xhtml", html)
        opf = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">'
            "  <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            f"    <dc:title>{title}</dc:title><dc:creator>{author}</dc:creator>"
            "    <dc:language>en</dc:language>"
            '    <dc:identifier id="uid">test-001</dc:identifier>'
            "  </metadata>"
            '  <manifest><item id="ch0" href="chapter0.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '  <spine><itemref idref="ch0"/></spine>'
            "</package>"
        )
        zf.writestr("OEBPS/content.opf", opf)
    return buf.getvalue()


def _make_source(storage_key: str) -> UploadedSourceArtifact:
    return UploadedSourceArtifact(
        artifact_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        storage_key=storage_key,
    )


class TestIngestStage:
    def test_returns_normalized_document(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/a"
        client.put(key, _make_epub())
        source = _make_source(key)

        doc = ingest(source, client)

        assert doc.title == "Test Book"
        assert doc.author == "Test Author"
        assert doc.source_type == "epub"
        assert doc.detected_language == "en"
        assert doc.source_word_count > 0
        assert doc.detection_confidence > 0.0

    def test_document_id_is_uuid(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/b"
        client.put(key, _make_epub())
        doc = ingest(_make_source(key), client)
        assert isinstance(doc.document_id, uuid.UUID)

    def test_chapter_refs_populated(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/c"
        client.put(key, _make_epub())
        doc = ingest(_make_source(key), client)
        assert len(doc.chapter_refs) >= 1

    def test_drm_epub_raises_drm_error(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/drm"
        client.put(key, _make_epub(include_drm=True))
        with pytest.raises(DrmDetectedError):
            ingest(_make_source(key), client)

    def test_missing_artifact_raises_lookup_error(self):
        client = FakeStorageClientWithBytes()
        source = _make_source("does/not/exist")
        with pytest.raises(LookupError):
            ingest(source, client)

    def test_corrupt_epub_raises_parse_error(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/corrupt"
        client.put(key, b"this is not an epub")
        with pytest.raises(EpubParseError):
            ingest(_make_source(key), client)

    def test_text_not_empty(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/d"
        client.put(key, _make_epub(chapter_text="Some text here " * 10))
        doc = ingest(_make_source(key), client)
        assert len(doc.text) > 0

    def test_word_count_matches_text(self):
        client = FakeStorageClientWithBytes()
        key = "users/u/jobs/j/source_epub/e"
        client.put(key, _make_epub())
        doc = ingest(_make_source(key), client)
        assert doc.source_word_count == len(doc.text.split())
