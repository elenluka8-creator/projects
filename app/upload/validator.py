"""EPUB upload validator.

Pure validation logic — no I/O, no DB, no storage calls.

Checks performed (in order):
1. File size ≤ 50 MB
2. Valid ZIP container
3. Entry count ≤ 10,000
4. Total uncompressed size ≤ 200 MB  (zip-bomb: expansion ratio ≤ 100:1)
5. HTML/XHTML content document count ≤ 1,000
6. EPUB MIME type declaration correct
7. DRM absence (META-INF/encryption.xml must not exist)
8. Spine item count ≤ 500

Returns ValidationResult(content_sha256, mime_type) on success.
Raises UploadValidationError(code, message) on any failure.
"""
from __future__ import annotations

import hashlib
import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

# Policy limits (configurable at module level for testing)
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024       # 50 MB
MAX_UNCOMPRESSED_BYTES: int = 200 * 1024 * 1024   # 200 MB
MAX_EXPANSION_RATIO: int = 100
MAX_ENTRY_COUNT: int = 10_000
MAX_HTML_FILES: int = 1_000
MAX_SPINE_ITEMS: int = 500

_EPUB_MIME_TYPE = "application/epub+zip"
_DRM_INDICATOR = "META-INF/encryption.xml"
_CONTAINER_XML = "META-INF/container.xml"


class UploadValidationError(Exception):
    """Raised when an uploaded file fails EPUB validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidationResult:
    content_sha256: str
    mime_type: str


def validate_epub_bytes(data: bytes) -> ValidationResult:
    """Validate raw EPUB bytes against all upload policy limits.

    Returns a ValidationResult on success.
    Raises UploadValidationError on any policy violation.
    """
    # 1. File size
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            "file_too_large",
            f"File size {len(data)} bytes exceeds the 50 MB limit.",
        )

    # 2. Compute SHA-256 (always, so we can return it on success)
    sha256 = hashlib.sha256(data).hexdigest()

    # 3. Valid ZIP
    try:
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
    except (zipfile.BadZipFile, Exception) as exc:
        raise UploadValidationError(
            "invalid_epub",
            "File is not a valid ZIP/EPUB archive.",
        ) from exc

    with zf:
        entries = zf.infolist()
        names = {e.filename for e in entries}

        # 4. Entry count
        if len(entries) > MAX_ENTRY_COUNT:
            raise UploadValidationError(
                "too_many_entries",
                f"Archive contains {len(entries)} entries; limit is {MAX_ENTRY_COUNT}.",
            )

        # 5. Uncompressed size + zip-bomb ratio
        total_uncompressed = sum(e.file_size for e in entries)
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise UploadValidationError(
                "archive_too_large",
                f"Total uncompressed size {total_uncompressed} bytes exceeds "
                f"the {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB limit.",
            )
        compressed_size = len(data)
        if compressed_size > 0 and (total_uncompressed / compressed_size) > MAX_EXPANSION_RATIO:
            raise UploadValidationError(
                "zip_bomb_detected",
                f"Archive expansion ratio exceeds {MAX_EXPANSION_RATIO}:1 limit.",
            )

        # 6. HTML file count
        html_count = sum(
            1
            for e in entries
            if e.filename.lower().endswith((".html", ".xhtml", ".htm"))
        )
        if html_count > MAX_HTML_FILES:
            raise UploadValidationError(
                "too_many_html_files",
                f"Archive contains {html_count} HTML/XHTML files; limit is {MAX_HTML_FILES}.",
            )

        # 7. EPUB MIME type (mimetype file, if present)
        if "mimetype" in names:
            try:
                mime_declared = zf.read("mimetype").strip().decode("ascii", errors="replace")
            except Exception:
                mime_declared = ""
            if mime_declared != _EPUB_MIME_TYPE:
                raise UploadValidationError(
                    "invalid_mime_type",
                    f"EPUB mimetype file declares '{mime_declared}'; "
                    f"expected '{_EPUB_MIME_TYPE}'.",
                )

        # 8. DRM detection
        if _DRM_INDICATOR in names:
            raise UploadValidationError(
                "drm_detected",
                "This EPUB contains DRM encryption. DRM-protected files cannot be processed.",
            )

        # 9. Spine item count
        spine_count = _count_spine_items(zf, names)
        if spine_count > MAX_SPINE_ITEMS:
            raise UploadValidationError(
                "too_many_chapters",
                f"EPUB spine has {spine_count} items; limit is {MAX_SPINE_ITEMS}.",
            )

    return ValidationResult(content_sha256=sha256, mime_type=_EPUB_MIME_TYPE)


def _count_spine_items(zf: zipfile.ZipFile, names: set) -> int:
    """Parse container.xml → OPF → spine to count spine items.

    Returns 0 if parsing fails (conservative — skip limit rather than reject).
    """
    if _CONTAINER_XML not in names:
        return 0
    try:
        container_data = zf.read(_CONTAINER_XML)
        root = ET.fromstring(container_data)
        ns = {"n": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rootfile = root.find(".//n:rootfile", ns)
        if rootfile is None:
            # Try without namespace
            rootfile = root.find(".//rootfile")
        if rootfile is None:
            return 0
        opf_path = rootfile.get("full-path", "")
        if not opf_path or opf_path not in names:
            return 0

        opf_data = zf.read(opf_path)
        opf_root = ET.fromstring(opf_data)

        # Try OPF namespace first, then without
        opf_ns = {"opf": "http://www.idpf.org/2007/opf"}
        spine = opf_root.find(".//opf:spine", opf_ns)
        if spine is None:
            spine = opf_root.find(".//spine")
        if spine is None:
            return 0
        return len(list(spine))
    except Exception:
        return 0
