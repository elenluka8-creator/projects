from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

SignedUrlPurpose = Literal["upload", "download"]


@dataclass(frozen=True)
class SignedUrlPolicyConfig:
    min_expiry_seconds: int
    max_expiry_seconds: int
    base_url: str

    @staticmethod
    def from_env() -> "SignedUrlPolicyConfig":
        return SignedUrlPolicyConfig(
            min_expiry_seconds=int(os.getenv("SIGNED_URL_MIN_EXPIRY_SECONDS", "60")),
            max_expiry_seconds=int(os.getenv("SIGNED_URL_MAX_EXPIRY_SECONDS", "900")),
            base_url=os.getenv("SIGNED_URL_BASE_URL", "https://storage.unfolda.local"),
        )


def _validate_expiry(expires_in_seconds: int, config: SignedUrlPolicyConfig) -> None:
    if expires_in_seconds < config.min_expiry_seconds:
        raise ValueError("Signed URL expiration is below minimum allowed.")
    if expires_in_seconds > config.max_expiry_seconds:
        raise ValueError("Signed URL expiration exceeds maximum allowed.")


def issue_signed_url(
    *,
    object_key: str,
    purpose: SignedUrlPurpose,
    expires_in_seconds: int,
    actor_id: Optional[uuid.UUID] = None,
    config: SignedUrlPolicyConfig | None = None,
) -> str:
    if not object_key.strip():
        raise ValueError("Object key must be provided.")

    policy_config = config or SignedUrlPolicyConfig.from_env()
    _validate_expiry(expires_in_seconds=expires_in_seconds, config=policy_config)

    escaped_object_key = quote(object_key.lstrip("/"), safe="/")
    path = f"/signed/{purpose}/{escaped_object_key}"
    query = urlencode({"purpose": purpose, "expires_in_seconds": expires_in_seconds})
    signed_url = f"{policy_config.base_url}{path}?{query}"

    if actor_id is not None:
        from app.security.audit_log import AUDIT_SIGNED_URL_ISSUED, emit_audit_event
        emit_audit_event(
            action=AUDIT_SIGNED_URL_ISSUED,
            actor_id=actor_id,
            target=object_key,
            extra={"purpose": purpose, "expires_in_seconds": expires_in_seconds},
        )

    return signed_url


def validate_signed_url_purpose(url: str, expected_purpose: SignedUrlPurpose) -> bool:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    actual_purpose = params.get("purpose", [None])[0]
    if actual_purpose != expected_purpose:
        return False
    return f"/signed/{expected_purpose}/" in parsed.path
