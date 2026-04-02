from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.artifact import ARTIFACT_TYPES, Artifact
from app.logging.structured import log_structured
from app.security.audit_log import AUDIT_SIGNED_URL_ISSUED, emit_audit_event
from app.security.signed_url_policy import SignedUrlPolicyConfig, _validate_expiry
from app.storage.client import StorageClientProtocol

import logging

logger = logging.getLogger(__name__)


def build_object_key(
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    artifact_type: str,
    artifact_id: uuid.UUID,
) -> str:
    """Return the canonical storage key for an artifact.

    Pattern: users/{user_id}/jobs/{job_id}/{artifact_type}/{artifact_id}
    """
    return f"users/{user_id}/jobs/{job_id}/{artifact_type}/{artifact_id}"


def register_artifact(
    session: Session,
    client: StorageClientProtocol,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    artifact_type: str,
    size_bytes: Optional[int],
    expires_in_seconds: int,
    policy_config: Optional[SignedUrlPolicyConfig] = None,
) -> Tuple[Artifact, str]:
    """Create an artifact DB record and issue a presigned upload URL.

    The DB record is created before the URL is returned — artifacts without
    a DB record are not canonical per DEC-004.

    Raises:
        ValueError: if artifact_type is invalid or expiry is out of policy bounds.
    """
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(
            f"Invalid artifact_type '{artifact_type}'. "
            f"Must be one of: {sorted(ARTIFACT_TYPES)}"
        )

    config = policy_config or SignedUrlPolicyConfig.from_env()
    _validate_expiry(expires_in_seconds=expires_in_seconds, config=config)

    artifact_id = uuid.uuid4()
    object_key = build_object_key(
        user_id=user_id,
        job_id=job_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
    )

    artifact = Artifact(
        artifact_id=artifact_id,
        user_id=user_id,
        job_id=job_id,
        artifact_type=artifact_type,
        object_key=object_key,
        size_bytes=size_bytes,
        storage_status="active",
    )
    session.add(artifact)
    session.flush()

    upload_url = client.get_presigned_upload_url(
        object_key=object_key,
        expires_in_seconds=expires_in_seconds,
    )

    emit_audit_event(
        action=AUDIT_SIGNED_URL_ISSUED,
        actor_id=user_id,
        target=object_key,
        extra={
            "purpose": "upload",
            "expires_in_seconds": expires_in_seconds,
            "artifact_type": artifact_type,
        },
    )

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="artifact_registered",
        payload={
            "artifact_id": str(artifact_id),
            "artifact_type": artifact_type,
            "user_id": str(user_id),
            "job_id": str(job_id),
        },
    )

    return artifact, upload_url


def issue_download_url(
    session: Session,
    client: StorageClientProtocol,
    artifact_id: uuid.UUID,
    user_id: uuid.UUID,
    expires_in_seconds: int,
    policy_config: Optional[SignedUrlPolicyConfig] = None,
) -> str:
    """Issue a presigned download URL for an artifact.

    Validates that the artifact exists, belongs to user_id, and is active.

    Raises:
        LookupError: if artifact does not exist or is deleted.
        PermissionError: if user_id does not own the artifact.
        ValueError: if expiry is out of policy bounds.
    """
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.storage_status == "deleted":
        raise LookupError(f"Artifact {artifact_id} not found or has been deleted.")

    if artifact.user_id != user_id:
        raise PermissionError(
            f"Artifact {artifact_id} does not belong to user {user_id}."
        )

    config = policy_config or SignedUrlPolicyConfig.from_env()
    _validate_expiry(expires_in_seconds=expires_in_seconds, config=config)

    download_url = client.get_presigned_download_url(
        object_key=artifact.object_key,
        expires_in_seconds=expires_in_seconds,
    )

    emit_audit_event(
        action=AUDIT_SIGNED_URL_ISSUED,
        actor_id=user_id,
        target=artifact.object_key,
        extra={
            "purpose": "download",
            "expires_in_seconds": expires_in_seconds,
            "artifact_id": str(artifact_id),
        },
    )

    return download_url


def mark_artifact_deleted(session: Session, artifact_id: uuid.UUID) -> None:
    """Mark an artifact as deleted. Does not remove the DB record.

    Called by the retention cleanup worker (FEAT-RETENTION), not exposed via API.
    """
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        return
    artifact.storage_status = "deleted"
    artifact.deleted_at = datetime.now(timezone.utc)
    session.flush()
