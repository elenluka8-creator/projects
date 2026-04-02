from __future__ import annotations

import uuid
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    require_artifact_ownership,
    require_job_ownership,
    require_object_key_ownership,
)
from app.api.errors import build_safe_error_detail
from app.security.audit_log import AUDIT_POLICY_REJECTED, emit_audit_event
from app.security.signed_url_policy import SignedUrlPurpose, issue_signed_url

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/jobs/{job_id}")
def get_job(
    job_id: uuid.UUID,
    _: uuid.UUID = Depends(require_job_ownership),
) -> Dict[str, str]:
    return {"job_id": str(job_id), "status": "owned"}


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: uuid.UUID,
    _: uuid.UUID = Depends(require_artifact_ownership),
) -> Dict[str, str]:
    return {"artifact_id": str(artifact_id), "status": "owned"}


@router.post("/signed-urls")
def create_signed_url(
    object_key: str = Query(..., min_length=1),
    purpose: SignedUrlPurpose = Query(...),
    expires_in_seconds: int = Query(default=300, ge=1),
    current_user_id: uuid.UUID = Depends(require_object_key_ownership),
) -> Dict[str, str]:
    try:
        signed_url = issue_signed_url(
            object_key=object_key,
            purpose=purpose,
            expires_in_seconds=expires_in_seconds,
            actor_id=current_user_id,
        )
    except ValueError as exc:
        emit_audit_event(
            action=AUDIT_POLICY_REJECTED,
            actor_id=current_user_id,
            target=object_key,
            reason="Signed URL policy violation.",
            extra={"purpose": purpose, "expires_in_seconds": expires_in_seconds},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_safe_error_detail(
                message="Signed URL policy violation.",
                context={
                    "object_key": object_key,
                    "purpose": purpose,
                    "expires_in_seconds": expires_in_seconds,
                },
            ),
        ) from exc

    return {
        "signed_url": signed_url,
        "object_key": object_key,
        "purpose": purpose,
        "expires_in_seconds": str(expires_in_seconds),
    }
