from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import build_safe_error_detail
from app.db.session import get_db_session
from app.storage.client import StorageClientProtocol, get_storage_client
from app.storage.service import issue_download_url, register_artifact

router = APIRouter(prefix="/storage", tags=["storage"])

_DEFAULT_UPLOAD_EXPIRY_SECONDS = 300
_DEFAULT_DOWNLOAD_EXPIRY_SECONDS = 300


class RegisterArtifactRequest(BaseModel):
    artifact_type: str
    job_id: uuid.UUID
    size_bytes: Optional[int] = None
    expires_in_seconds: int = _DEFAULT_UPLOAD_EXPIRY_SECONDS


class RegisterArtifactResponse(BaseModel):
    artifact_id: str
    object_key: str
    upload_url: str
    expires_in_seconds: int


class DownloadUrlResponse(BaseModel):
    artifact_id: str
    object_key: str
    download_url: str
    expires_in_seconds: int


@router.post("/artifacts", response_model=RegisterArtifactResponse)
def create_artifact(
    body: RegisterArtifactRequest,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage_client: StorageClientProtocol = Depends(get_storage_client),
) -> RegisterArtifactResponse:
    """Register an artifact and issue a presigned upload URL.

    The DB record is created before the URL is returned (register-before-use).
    The client uploads directly to object storage using the returned upload_url.
    """
    try:
        artifact, upload_url = register_artifact(
            session=session,
            client=storage_client,
            user_id=current_user_id,
            job_id=body.job_id,
            artifact_type=body.artifact_type,
            size_bytes=body.size_bytes,
            expires_in_seconds=body.expires_in_seconds,
        )
        session.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_safe_error_detail(
                message=str(exc),
                context={
                    "artifact_type": body.artifact_type,
                    "job_id": str(body.job_id),
                    "expires_in_seconds": body.expires_in_seconds,
                },
            ),
        ) from exc

    return RegisterArtifactResponse(
        artifact_id=str(artifact.artifact_id),
        object_key=artifact.object_key,
        upload_url=upload_url,
        expires_in_seconds=body.expires_in_seconds,
    )


@router.get(
    "/artifacts/{artifact_id}/download-url",
    response_model=DownloadUrlResponse,
)
def get_download_url(
    artifact_id: uuid.UUID,
    expires_in_seconds: int = _DEFAULT_DOWNLOAD_EXPIRY_SECONDS,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage_client: StorageClientProtocol = Depends(get_storage_client),
) -> DownloadUrlResponse:
    """Issue a presigned download URL for an owned artifact."""
    try:
        download_url = issue_download_url(
            session=session,
            client=storage_client,
            artifact_id=artifact_id,
            user_id=current_user_id,
            expires_in_seconds=expires_in_seconds,
        )
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
                context={
                    "artifact_id": str(artifact_id),
                    "expires_in_seconds": expires_in_seconds,
                },
            ),
        ) from exc

    # Fetch artifact metadata for response (we already validated ownership above)
    from app.db.models.artifact import Artifact

    artifact = session.get(Artifact, artifact_id)

    return DownloadUrlResponse(
        artifact_id=str(artifact_id),
        object_key=artifact.object_key,  # type: ignore[union-attr]
        download_url=download_url,
        expires_in_seconds=expires_in_seconds,
    )
