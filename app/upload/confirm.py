"""Upload confirm domain service.

After a client uploads an EPUB to object storage via a presigned URL,
this service is called to validate the artifact:

1. Fetch artifact record; verify ownership and type == source_epub.
2. Guard against re-confirming an already-validated artifact (idempotent).
3. Download bytes from storage.
4. Run validate_epub_bytes() — all abuse-protection and structure checks.
5. On success: stamp content_sha256, mime_type, validated_at, authoritative size_bytes.
6. On UploadValidationError: mark artifact deleted; re-raise so the caller can
   return a structured 422 to the client.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.artifact import Artifact
from app.logging.structured import log_structured
from app.storage.client import StorageClientProtocol
from app.upload.validator import UploadValidationError, validate_epub_bytes

logger = logging.getLogger(__name__)


def confirm_upload(
    session: Session,
    client: StorageClientProtocol,
    artifact_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Artifact:
    """Validate an uploaded source_epub artifact and update its DB record.

    Returns the updated Artifact on success.

    Raises:
        LookupError:            artifact not found or already deleted.
        PermissionError:        user does not own the artifact.
        ValueError:             artifact_type is not source_epub.
        UploadValidationError:  EPUB failed validation (artifact marked deleted).
    """
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.storage_status == "deleted":
        raise LookupError(f"Artifact {artifact_id} not found or has been deleted.")

    if artifact.user_id != user_id:
        raise PermissionError(
            f"Artifact {artifact_id} does not belong to the requesting user."
        )

    if artifact.artifact_type != "source_epub":
        raise ValueError(
            f"Expected artifact_type 'source_epub', got '{artifact.artifact_type}'."
        )

    # Idempotent: already confirmed
    if artifact.validated_at is not None:
        return artifact

    # Fetch bytes from storage
    data = client.get_object_bytes(artifact.object_key)

    # Validate EPUB — may raise UploadValidationError
    try:
        result = validate_epub_bytes(data)
    except UploadValidationError:
        artifact.storage_status = "deleted"
        artifact.deleted_at = datetime.now(timezone.utc)
        session.flush()
        log_structured(
            logger=logger,
            level=logging.WARNING,
            message="epub_upload_validation_failed",
            payload={
                "artifact_id": str(artifact_id),
                "user_id": str(user_id),
            },
        )
        raise

    # Stamp validation metadata
    artifact.content_sha256 = result.content_sha256
    artifact.mime_type = result.mime_type
    artifact.validated_at = datetime.now(timezone.utc)
    artifact.size_bytes = len(data)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="epub_upload_confirmed",
        payload={
            "artifact_id": str(artifact_id),
            "user_id": str(user_id),
            "size_bytes": len(data),
            "content_sha256": result.content_sha256,
        },
    )

    return artifact
