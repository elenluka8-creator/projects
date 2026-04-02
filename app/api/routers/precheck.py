"""Pre-submission analysis router (FEAT-PRECHECK).

POST /precheck/{artifact_id} — run (or return cached) PRECHECK for a validated source EPUB.
GET  /precheck/{artifact_id} — retrieve an existing PRECHECK result.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import build_safe_error_detail
from app.db.models.precheck import PreCheckResult
from app.db.session import get_db_session
from app.precheck.service import run_precheck
from app.storage.client import StorageClientProtocol, get_storage_client

router = APIRouter(prefix="/precheck", tags=["precheck"])


class PreCheckResponse(BaseModel):
    precheck_id: str
    artifact_id: str
    status: str
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = None
    word_count: Optional[int] = None
    chapter_count: Optional[int] = None
    has_images: Optional[bool] = None
    error_code: Optional[str] = None
    completed_at: Optional[str] = None


def _to_response(record: PreCheckResult) -> PreCheckResponse:
    return PreCheckResponse(
        precheck_id=str(record.precheck_id),
        artifact_id=str(record.artifact_id),
        status=record.status,
        detected_language=record.detected_language,
        language_confidence=record.language_confidence,
        word_count=record.word_count,
        chapter_count=record.chapter_count,
        has_images=record.has_images,
        error_code=record.error_code,
        completed_at=(
            record.completed_at.isoformat() if record.completed_at is not None else None
        ),
    )


@router.post(
    "/{artifact_id}",
    response_model=PreCheckResponse,
    summary="Run pre-submission analysis for a validated source EPUB",
)
def trigger_precheck(
    artifact_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    storage_client: StorageClientProtocol = Depends(get_storage_client),
) -> PreCheckResponse:
    """Trigger pre-submission analysis. Idempotent — returns cached result if available.

    Returns 200 on success (even when status='failed' — that is a valid terminal state).
    Returns 404 if the artifact does not exist.
    Returns 403 if the artifact belongs to another user.
    Returns 400 if the artifact has not been validated or is not a source_epub.
    """
    try:
        record = run_precheck(
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

    return _to_response(record)


@router.get(
    "/{artifact_id}",
    response_model=PreCheckResponse,
    summary="Retrieve an existing pre-submission analysis result",
)
def get_precheck(
    artifact_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PreCheckResponse:
    """Return the existing PRECHECK result for the given artifact.

    Returns 404 if no result exists (trigger via POST first).
    Returns 403 if the result belongs to another user.
    """
    record: Optional[PreCheckResult] = session.execute(
        select(PreCheckResult).where(PreCheckResult.artifact_id == artifact_id)
    ).scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="No pre-check result found for this artifact.",
                context={"artifact_id": str(artifact_id)},
            ),
        )

    if record.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Forbidden.",
                context={"artifact_id": str(artifact_id)},
            ),
        )

    return _to_response(record)
