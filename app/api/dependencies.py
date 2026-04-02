from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.api.errors import build_safe_error_detail
from app.db.models.user import User
from app.db.session import get_db_session


def decode_bearer_jwt(authorization: Optional[str]) -> dict[str, Any]:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header.",
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme.",
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    secret = os.getenv("NEXTAUTH_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured.",
        )

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc

    return payload


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> uuid.UUID:
    payload = decode_bearer_jwt(authorization=authorization)

    raw_user_id = payload.get("user_id")
    if raw_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user_id.",
        )

    try:
        return uuid.UUID(str(raw_user_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload has invalid user_id.",
        ) from exc


def require_admin(
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> uuid.UUID:
    user = session.get(User, current_user_id)
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user_id


@dataclass
class InMemoryOwnershipStore:
    job_owners: Dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    artifact_owners: Dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    object_owners: Dict[str, uuid.UUID] = field(default_factory=dict)

    def get_job_owner_id(self, job_id: uuid.UUID) -> Optional[uuid.UUID]:
        return self.job_owners.get(job_id)

    def get_artifact_owner_id(self, artifact_id: uuid.UUID) -> Optional[uuid.UUID]:
        return self.artifact_owners.get(artifact_id)

    def get_object_owner_id(self, object_key: str) -> Optional[uuid.UUID]:
        return self.object_owners.get(object_key)


_ownership_store = InMemoryOwnershipStore()


def get_ownership_store() -> InMemoryOwnershipStore:
    return _ownership_store


def require_job_ownership(
    job_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    ownership_store: InMemoryOwnershipStore = Depends(get_ownership_store),
) -> uuid.UUID:
    owner_user_id = ownership_store.get_job_owner_id(job_id)
    if owner_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id), "resource_type": "job"},
            ),
        )
    if owner_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Forbidden.",
                context={"job_id": str(job_id), "resource_type": "job"},
            ),
        )
    return current_user_id


def require_artifact_ownership(
    artifact_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user),
    ownership_store: InMemoryOwnershipStore = Depends(get_ownership_store),
) -> uuid.UUID:
    owner_user_id = ownership_store.get_artifact_owner_id(artifact_id)
    if owner_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Artifact not found.",
                context={"artifact_id": str(artifact_id), "resource_type": "artifact"},
            ),
        )
    if owner_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Forbidden.",
                context={"artifact_id": str(artifact_id), "resource_type": "artifact"},
            ),
        )
    return current_user_id


def require_object_key_ownership(
    object_key: str,
    current_user_id: uuid.UUID = Depends(get_current_user),
    ownership_store: InMemoryOwnershipStore = Depends(get_ownership_store),
) -> uuid.UUID:
    owner_user_id = ownership_store.get_object_owner_id(object_key)
    if owner_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Object not found.",
                context={"object_key": object_key, "resource_type": "object"},
            ),
        )
    if owner_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_safe_error_detail(
                message="Forbidden.",
                context={"object_key": object_key, "resource_type": "object"},
            ),
        )
    return current_user_id
