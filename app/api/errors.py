from __future__ import annotations

from typing import Any, Dict

from app.security.payload_guard import sanitize_for_error_payload


def build_safe_error_detail(message: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = sanitize_for_error_payload(context or {})
    return {"message": message, "context": payload}
