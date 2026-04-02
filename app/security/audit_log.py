from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logging.structured import log_structured

logger = logging.getLogger(__name__)

AuditAction = str

AUDIT_SIGNED_URL_ISSUED = "signed_url_issued"
AUDIT_POLICY_REJECTED = "policy_rejected"
AUDIT_BREAK_GLASS_ACCESS = "break_glass_access"
AUDIT_ADMIN_CREDIT_ADJUST = "admin_credit_adjustment"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_audit_event(
    action: AuditAction,
    actor_id: uuid.UUID,
    target: str,
    reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a durable, metadata-only audit record.

    Fields:
    - action: one of AUDIT_* constants
    - actor_id: UUID of the authenticated user performing the action
    - target: resource identifier (object_key, policy name, etc.) — no raw content
    - reason: human-readable reason string (required for break-glass)
    - extra: additional metadata-only context fields
    """
    record: Dict[str, Any] = {
        "audit": True,
        "action": action,
        "actor_id": str(actor_id),
        "target": target,
        "timestamp": _now_iso(),
    }
    if reason is not None:
        record["reason"] = reason
    if extra:
        record.update(extra)

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="audit_event",
        payload=record,
    )


def emit_break_glass_audit_event(
    actor_id: uuid.UUID,
    target: str,
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit a mandatory break-glass audit event.

    Break-glass events always require an explicit reason and are
    logged at WARNING level to ensure visibility.
    """
    if not reason.strip():
        raise ValueError("Break-glass audit event requires a non-empty reason.")

    record: Dict[str, Any] = {
        "audit": True,
        "action": AUDIT_BREAK_GLASS_ACCESS,
        "actor_id": str(actor_id),
        "target": target,
        "reason": reason,
        "timestamp": _now_iso(),
        "break_glass": True,
    }
    if extra:
        record.update(extra)

    log_structured(
        logger=logger,
        level=logging.WARNING,
        message="break_glass_audit_event",
        payload=record,
    )
