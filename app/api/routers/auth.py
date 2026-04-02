from __future__ import annotations

from typing import Dict, Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.errors import build_safe_error_detail
from app.api.dependencies import decode_bearer_jwt
from app.db.session import get_db_session
from app.domain.services.user_service import IdentityClaims, provision_user

router = APIRouter(prefix="/auth", tags=["auth"])


def get_identity_claims(
    authorization: Optional[str] = Header(default=None),
) -> IdentityClaims:
    payload = decode_bearer_jwt(authorization=authorization)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    display_name = payload.get("name")

    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_safe_error_detail(
                message="Identity token missing required claims.",
                context={
                    "google_sub_present": bool(google_sub),
                    "email_present": bool(email),
                    "claim_keys": sorted(payload.keys()),
                },
            ),
        )

    return IdentityClaims(
        google_sub=str(google_sub),
        email=str(email),
        display_name=str(display_name) if display_name else None,
    )


@router.post("/provision")
def provision(
    identity: IdentityClaims = Depends(get_identity_claims),
    session: Session = Depends(get_db_session),
) -> Dict[str, Union[str, bool]]:
    result = provision_user(session=session, identity=identity)
    return {"user_id": str(result.user_id), "is_new_user": result.is_new_user}
