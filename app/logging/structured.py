from __future__ import annotations

import logging
from typing import Any, Dict

from app.security.payload_guard import sanitize_for_logging_payload


def log_structured(
    logger: logging.Logger,
    level: int,
    message: str,
    payload: Dict[str, Any] | None = None,
    exc_info: bool = False,
) -> None:
    safe_payload = sanitize_for_logging_payload(payload or {})
    logger.log(level, message, extra=safe_payload, exc_info=exc_info)
