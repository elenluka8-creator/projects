from __future__ import annotations

from typing import Any, Dict

REDACTION_MARKER = "[REDACTED_RAW_TEXT]"

FORBIDDEN_FIELD_NAMES = {
    "text",
    "raw_text",
    "source_text",
    "translated_text",
    "paragraph",
    "paragraph_text",
    "original_text",
    "book_text",
    "content",
}


def _is_forbidden_key(key: str) -> bool:
    normalized = key.strip().lower()
    if normalized in FORBIDDEN_FIELD_NAMES:
        return True
    return normalized.endswith("_text") or normalized.endswith("_content")


def _looks_like_raw_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    trimmed = value.strip()
    if not trimmed:
        return False
    # Heuristic: long free-form sentence/paragraph-like string.
    return len(trimmed) > 120 and " " in trimmed


def contains_forbidden_content(payload: Dict[str, Any]) -> bool:
    for key, value in payload.items():
        if _is_forbidden_key(key):
            return True
        if isinstance(value, dict) and contains_forbidden_content(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and contains_forbidden_content(item):
                    return True
                if _looks_like_raw_text(item):
                    return True
        if _looks_like_raw_text(value):
            return True
    return False


def _sanitize_value(key: str, value: Any) -> Any:
    if _is_forbidden_key(key):
        return REDACTION_MARKER
    if isinstance(value, dict):
        return sanitize_for_logging_payload(value)
    if isinstance(value, list):
        sanitized_list = []
        for item in value:
            if isinstance(item, dict):
                sanitized_list.append(sanitize_for_logging_payload(item))
            elif _looks_like_raw_text(item):
                sanitized_list.append(REDACTION_MARKER)
            else:
                sanitized_list.append(item)
        return sanitized_list
    if _looks_like_raw_text(value):
        return REDACTION_MARKER
    return value


def sanitize_for_logging_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        sanitized[key] = _sanitize_value(key, value)
    return sanitized


def sanitize_for_error_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Same deterministic policy as logging for forbidden content.
    return sanitize_for_logging_payload(payload)
