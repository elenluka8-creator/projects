from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Literal, TypedDict
from uuid import UUID

from app.logging.structured import log_structured
from app.security.payload_guard import contains_forbidden_content

logger = logging.getLogger(__name__)

AuthEventName = Literal["user_registered", "user_signed_in"]


class AuthEventPayload(TypedDict):
    event_name: AuthEventName
    user_id: str
    timestamp: str


def emit_event(event_name: AuthEventName, user_id: UUID) -> None:
    """Fire-and-forget auth analytics event.

    Event schema:
    - event_name: "user_registered" | "user_signed_in"
    - user_id: UUID string
    - timestamp: ISO-8601 UTC timestamp
    """
    try:
        payload: Dict[str, str] = AuthEventPayload(
            event_name=event_name,
            user_id=str(user_id),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if contains_forbidden_content(payload):
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="Analytics payload rejected by payload guard.",
                payload={"event_name": event_name, "user_id": str(user_id)},
            )
            return
        log_structured(
            logger=logger,
            level=logging.INFO,
            message="analytics_event",
            payload=payload,
        )
    except Exception:
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="Failed to emit analytics event.",
            payload={"event_name": event_name, "user_id": str(user_id)},
            exc_info=True,
        )
