"""Tests for ingestion data models."""
from __future__ import annotations

import uuid

import pytest

from app.pipeline.ingestion.models import (
    ChapterRef,
    DrmDetectedError,
    EpubParseError,
    IngestionError,
    NormalizedDocument,
    StructuralRef,
    UploadedSourceArtifact,
)


def _make_artifact(**kwargs) -> UploadedSourceArtifact:
    defaults = dict(
        artifact_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        storage_key="users/u/jobs/j/source_epub/a",
    )
    defaults.update(kwargs)
    return UploadedSourceArtifact(**defaults)


def _make_doc(**kwargs) -> NormalizedDocument:
    defaults = dict(
        document_id=uuid.uuid4(),
        source_type="epub",
        title="Test Book",
        author="Test Author",
        text="Hello world.",
        detected_language="en",
        detection_confidence=0.99,
        source_word_count=2,
    )
    defaults.update(kwargs)
    return NormalizedDocument(**defaults)


class TestUploadedSourceArtifact:
    def test_default_source_type_and_mime(self):
        a = _make_artifact()
        assert a.source_type == "epub"
        assert a.mime_type == "application/epub+zip"

    def test_all_fields_accessible(self):
        uid = uuid.uuid4()
        jid = uuid.uuid4()
        aid = uuid.uuid4()
        a = UploadedSourceArtifact(
            artifact_id=aid,
            user_id=uid,
            job_id=jid,
            storage_key="users/u/jobs/j/source_epub/a",
        )
        assert a.artifact_id == aid
        assert a.user_id == uid
        assert a.job_id == jid
        assert a.storage_key == "users/u/jobs/j/source_epub/a"

    def test_frozen(self):
        a = _make_artifact()
        with pytest.raises((AttributeError, TypeError)):
            a.source_type = "pdf"  # type: ignore[misc]


class TestChapterRef:
    def test_fields(self):
        c = ChapterRef(chapter_id="ch1", title="Chapter One", order=0)
        assert c.chapter_id == "ch1"
        assert c.title == "Chapter One"
        assert c.order == 0

    def test_frozen(self):
        c = ChapterRef(chapter_id="ch1", title="Chapter One", order=0)
        with pytest.raises((AttributeError, TypeError)):
            c.order = 1  # type: ignore[misc]


class TestStructuralRef:
    def test_image_ref(self):
        r = StructuralRef(ref_type="image", href="images/cover.jpg")
        assert r.ref_type == "image"
        assert r.href == "images/cover.jpg"

    def test_stylesheet_ref(self):
        r = StructuralRef(ref_type="stylesheet", href="styles/main.css")
        assert r.ref_type == "stylesheet"


class TestNormalizedDocument:
    def test_required_fields(self):
        doc = _make_doc()
        assert doc.source_type == "epub"
        assert doc.title == "Test Book"
        assert doc.source_word_count == 2

    def test_default_empty_collections(self):
        doc = _make_doc()
        assert doc.chapter_refs == []
        assert doc.structural_refs == []
        assert doc.metadata == {}

    def test_with_chapter_refs(self):
        refs = [ChapterRef(chapter_id="c1", title="Ch 1", order=0)]
        doc = _make_doc(chapter_refs=refs)
        assert len(doc.chapter_refs) == 1
        assert doc.chapter_refs[0].chapter_id == "c1"

    def test_frozen(self):
        doc = _make_doc()
        with pytest.raises((AttributeError, TypeError)):
            doc.title = "Other"  # type: ignore[misc]

    def test_immutable_collections_via_replace(self):
        doc = _make_doc()
        from dataclasses import replace
        doc2 = replace(doc, title="New Title")
        assert doc2.title == "New Title"
        assert doc.title == "Test Book"


class TestErrors:
    def test_drm_error_is_ingestion_error(self):
        err = DrmDetectedError("drm found")
        assert isinstance(err, IngestionError)

    def test_epub_parse_error_is_ingestion_error(self):
        err = EpubParseError("bad epub")
        assert isinstance(err, IngestionError)

    def test_error_message_preserved(self):
        err = DrmDetectedError("encryption.xml detected")
        assert "encryption.xml" in str(err)
