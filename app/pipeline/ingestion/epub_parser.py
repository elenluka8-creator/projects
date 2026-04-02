"""EPUB parser for the ingestion stage.

Responsibilities:
- Detect DRM-protected EPUBs and raise DrmDetectedError immediately
- Parse EPUB structure using ebooklib + BeautifulSoup
- Extract full text, chapter references, structural references, and OPF metadata
- Count source words

No LLM calls. No downstream stage calls. No external I/O beyond the bytes passed in.
"""
from __future__ import annotations

import io
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List

from app.pipeline.ingestion.models import (
    ChapterRef,
    DrmDetectedError,
    EpubParseError,
    StructuralRef,
)

# Item types that ebooklib considers document content
_DOCUMENT_MEDIA_TYPES = frozenset(
    {
        "application/xhtml+xml",
        "text/html",
    }
)

_IMAGE_MEDIA_TYPE_PREFIXES = ("image/",)
_STYLESHEET_MEDIA_TYPES = frozenset({"text/css"})

# Block-level HTML elements whose text content forms one paragraph each.
# Inline elements (em, strong, span, a, ruby, …) are intentionally absent —
# they are merged into the surrounding block by _extract_chapter_text().
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "dt", "dd", "td", "th",
    "blockquote", "pre", "address", "caption",
})

_DRM_INDICATOR_PATH = "META-INF/encryption.xml"


@dataclass
class ParsedEpub:
    """Intermediate result of EPUB parsing before language detection."""

    title: str
    author: str
    text: str
    chapter_refs: List[ChapterRef] = field(default_factory=list)
    structural_refs: List[StructuralRef] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    source_word_count: int = 0


def parse(epub_bytes: bytes) -> ParsedEpub:
    """Parse raw EPUB bytes into a ParsedEpub.

    Raises:
        DrmDetectedError: if encryption.xml is present in the container.
        EpubParseError: if the bytes are not a valid EPUB.
    """
    _check_drm(epub_bytes)

    try:
        import ebooklib
        from ebooklib import epub as eblib_epub
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise EpubParseError(
            f"Required parsing library not available: {exc}"
        ) from exc

    try:
        book = eblib_epub.read_epub(io.BytesIO(epub_bytes), options={"ignore_ncx": False})
    except Exception as exc:
        raise EpubParseError(f"Failed to parse EPUB: {exc}") from exc

    title = _get_metadata_value(book, "DC", "title") or "Unknown Title"
    author = _get_metadata_value(book, "DC", "creator") or "Unknown Author"
    language = _get_metadata_value(book, "DC", "language") or ""

    chapter_texts: List[str] = []
    chapter_refs: List[ChapterRef] = []
    structural_refs: List[StructuralRef] = []

    spine_ids = [item_id for item_id, _ in book.spine]

    for order, item_id in enumerate(spine_ids):
        item = book.get_item_with_id(item_id)
        if item is None:
            continue

        media_type = item.media_type or ""

        if media_type in _DOCUMENT_MEDIA_TYPES:
            try:
                soup = BeautifulSoup(item.get_body_content(), "lxml")
                chapter_text = _extract_chapter_text(soup)
            except Exception:
                chapter_text = ""

            chapter_title = _extract_chapter_title(item, order)
            chapter_refs.append(
                ChapterRef(chapter_id=item.id, title=chapter_title, order=order)
            )
            if chapter_text:
                chapter_texts.append(chapter_text)

    for item in book.get_items():
        media_type = item.media_type or ""
        href = item.file_name or ""
        if any(media_type.startswith(p) for p in _IMAGE_MEDIA_TYPE_PREFIXES):
            structural_refs.append(StructuralRef(ref_type="image", href=href))
        elif media_type in _STYLESHEET_MEDIA_TYPES:
            structural_refs.append(StructuralRef(ref_type="stylesheet", href=href))

    full_text = "\n\n".join(chapter_texts)
    word_count = len(full_text.split()) if full_text else 0

    metadata: Dict[str, str] = {}
    if language:
        metadata["epub_language"] = language
    publisher = _get_metadata_value(book, "DC", "publisher")
    if publisher:
        metadata["publisher"] = publisher

    return ParsedEpub(
        title=title,
        author=author,
        text=full_text,
        chapter_refs=chapter_refs,
        structural_refs=structural_refs,
        metadata=metadata,
        source_word_count=word_count,
    )



def _extract_chapter_text(soup) -> str:
    """Extract plain text from an EPUB chapter preserving paragraph structure.

    Locates *leaf* block elements — block elements that contain no other block
    elements — and extracts their full text using separator=" " so that inline
    elements (em, strong, span, ruby, a, …) are merged into a single line per
    paragraph. Only newlines *between* paragraphs are preserved.

    Without this, BeautifulSoup's get_text(separator="\n") inserts a newline
    at every tag boundary, including inline tags. A paragraph like
    "<p>Hello <em>world</em>!</p>" becomes three separate lines: "Hello",
    "world", "!" — each turned into its own segment and its own output block,
    visible as one word (or character) per line in the translated EPUB.
    """
    body = soup.find("body") or soup
    block_tag_list = list(_BLOCK_TAGS)
    paragraphs: list = []

    for elem in body.find_all(block_tag_list):
        # Only process *leaf* block elements (no block-element children) to
        # avoid duplicating text from container divs that wrap other blocks.
        if elem.find(block_tag_list):
            continue
        # Merge inline content; collapse any extra whitespace.
        text = " ".join(elem.get_text(separator=" ", strip=True).split())
        if text:
            paragraphs.append(text)

    if not paragraphs:
        # Fallback for unusual EPUB structure with no recognisable block elements.
        raw = soup.get_text(separator="\n", strip=True)
        paragraphs = [line.strip() for line in raw.splitlines() if line.strip()]

    paragraphs = _condense_single_char_paragraphs(paragraphs)
    return "\n".join(_coalesce_punctuation_paragraphs(paragraphs))




def _condense_single_char_paragraphs(paragraphs: list) -> list:
    """Concatenate runs of single-character paragraphs into words or phrases.

    Some EPUB conversion tools wrap each character in its own block element,
    for example:

        <div>T</div><div>h</div><div>e</div>

    After leaf-block extraction each such element becomes a one-character
    paragraph.  Three or more consecutive single-character paragraphs are
    joined *without* a separator (direct concatenation), reconstructing the
    original word or phrase.

    Isolated or paired single-character paragraphs — e.g. a Roman-numeral
    heading ("I", "V") or a short dialogue marker ("—") — are left unchanged
    so they are handled by _coalesce_punctuation_paragraphs or kept as-is.
    """
    if not paragraphs:
        return paragraphs

    result: list = []
    run: list = []

    for para in paragraphs:
        if len(para) == 1:
            run.append(para)
        else:
            if len(run) >= 3:
                result.append("".join(run))
            else:
                result.extend(run)
            run = []
            result.append(para)

    # Flush any trailing single-char run.
    if len(run) >= 3:
        result.append("".join(run))
    else:
        result.extend(run)

    return result


def _coalesce_punctuation_paragraphs(paragraphs: list) -> list:
    """Merge punctuation-only paragraphs into adjacent content paragraphs.

    Some EPUBs wrap punctuation marks such as «, », (, ) in their own block
    elements (e.g. <p>«</p>).  Without this step each such element becomes its
    own segment and — after translation — its own output block, appearing as a
    lone punctuation character on a separate line.

    Strategy (one forward pass + one backward pass):
    - Forward: opening punctuation (Unicode Pi / Ps: «, (, [, …) is collected
      as a *pending prefix* and prepended to the next content paragraph.
    - Backward: remaining punctuation-only paragraphs (closing: », ), ] or
      other) are appended to the preceding content paragraph.

    A paragraph is considered "punctuation-only" if it contains no letter or
    digit characters (as determined by str.isalpha() / str.isdigit()).
    """
    if not paragraphs:
        return paragraphs

    _OPENING_CATS = frozenset({"Pi", "Ps"})   # «, (, [, {, …
    _CLOSING_CATS = frozenset({"Pf", "Pe"})   # », ), ], }, …

    def _has_content(text: str) -> bool:
        return any(c.isalpha() or c.isdigit() for c in text)

    def _is_opening(text: str) -> bool:
        cats = {unicodedata.category(c) for c in text if not c.isspace()}
        return bool(cats & _OPENING_CATS) and not bool(cats & _CLOSING_CATS)

    # Forward pass — collect opening-punctuation prefixes.
    forward: list = []
    pending: str = ""
    for para in paragraphs:
        if not _has_content(para) and _is_opening(para):
            pending += para
        else:
            forward.append(pending + para if pending else para)
            pending = ""
    if pending:
        # Dangling opening punctuation (no following content) → append to last.
        if forward:
            forward[-1] += pending
        else:
            forward.append(pending)

    # Backward pass — append remaining punctuation-only items to the previous.
    result: list = []
    for para in forward:
        if not _has_content(para) and result:
            result[-1] += para
        else:
            result.append(para)

    return result


def _check_drm(epub_bytes: bytes) -> None:
    """Raise DrmDetectedError if the EPUB zip contains encryption.xml."""
    try:
        with zipfile.ZipFile(io.BytesIO(epub_bytes)) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise EpubParseError("File is not a valid ZIP/EPUB container.") from exc
    except Exception as exc:
        raise EpubParseError(f"Cannot read EPUB container: {exc}") from exc

    if _DRM_INDICATOR_PATH in names:
        raise DrmDetectedError(
            "EPUB contains META-INF/encryption.xml — DRM-protected content is not supported."
        )


def _get_metadata_value(book: object, namespace: str, name: str) -> str:
    """Extract the first metadata value for (namespace, name), or empty string."""
    try:
        items = book.get_metadata(namespace, name)  # type: ignore[attr-defined]
        if items:
            value, _ = items[0]
            return str(value).strip()
    except Exception:
        pass
    return ""


def _extract_chapter_title(item: object, fallback_order: int) -> str:
    """Attempt to extract a chapter title from the HTML content."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(item.get_body_content(), "lxml")  # type: ignore[attr-defined]
        heading = soup.find(["h1", "h2", "h3", "title"])
        if heading:
            return heading.get_text(strip=True)
    except Exception:
        pass
    return f"Chapter {fallback_order + 1}"
