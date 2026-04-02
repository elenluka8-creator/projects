"""Upload router — EPUB upload confirmation endpoint.

The upload session (presigned PUT URL + artifact registration) is handled by
POST /storage/artifacts (FEAT-STORAGE). This router adds the confirmation step
that validates the uploaded EPUB bytes and finalises artifact metadata.
"""
from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import build_safe_error_detail
from app.db.session import get_db_session
from app.storage.client import StorageClientProtocol, get_storage_client
from app.upload.confirm import confirm_upload
from app.upload.validator import UploadValidationError

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadConfirmResponse(BaseModel):
    artifact_id: str
    object_key: str
    content_sha256: str
    mime_type: str
    size_bytes: int
    validated_at: str


@router.post(
    "/confirm/{artifact_id}",
    response_model=UploadConfirmResponse,
    summary="Confirm and validate an uploaded source EPUB",
)
def confirm_upload_endpoint(
    artifact_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage_client: StorageClientProtocol = Depends(get_storage_client),
) -> UploadConfirmResponse:
    """Fetch the uploaded EPUB from storage, validate it, and stamp artifact metadata.

    Must be called after the client has PUT the file to the presigned URL returned
    by POST /storage/artifacts.

    Returns 200 with artifact details on success.
    Returns 404 if the artifact does not exist.
    Returns 403 if the artifact belongs to another user.
    Returns 422 if the EPUB fails validation (file too large, DRM, zip bomb, etc.).
    """
    try:
        artifact = confirm_upload(
            session=session,
            client=storage_client,
            artifact_id=artifact_id,
            user_id=current_user_id,
        )
        session.commit()
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Artifact not found.",
                context={"artifact_id": str(artifact_id)},
            ),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Forbidden.",
                context={"artifact_id": str(artifact_id)},
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_safe_error_detail(
                message=str(exc),
                context={"artifact_id": str(artifact_id)},
            ),
        ) from exc
    except UploadValidationError as exc:
        session.commit()  # persist the deletion marker
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_safe_error_detail(
                message=exc.message,
                context={
                    "code": exc.code,
                    "artifact_id": str(artifact_id),
                },
            ),
        ) from exc

    validated_at_str = (
        artifact.validated_at.replace(tzinfo=timezone.utc).isoformat()
        if artifact.validated_at is not None
        else ""
    )
    return UploadConfirmResponse(
        artifact_id=str(artifact.artifact_id),
        object_key=artifact.object_key,
        content_sha256=artifact.content_sha256 or "",
        mime_type=artifact.mime_type or "",
        size_bytes=artifact.size_bytes or 0,
        validated_at=validated_at_str,
    )
