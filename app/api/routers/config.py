"""Config router — translation configuration estimation and validation.

POST /config/estimate — estimate credit cost and validate config without creating a job.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.config.policy import (
    ConfigValidationError,
    estimate_credits,
    get_confidence_label,
    get_language_pair_tier,
    validate_job_config,
)

router = APIRouter(prefix="/config", tags=["config"])


class EstimateRequest(BaseModel):
    word_count: int
    mode: str
    target_language: str
    source_language: Optional[str] = None
    translation_style: str = "natural"
    user_level: str = "B1"
    explanation_depth: str = "standard"
    quality_tier: str = "standard"
    # Optional: pass PRECHECK confidence to get a confidence label in the response
    source_language_confidence: Optional[float] = None


class EstimateResponse(BaseModel):
    estimated_credits: int
    language_pair_tier: str
    source_language_confidence_label: Optional[str]
    is_valid: bool
    validation_errors: List[str]


@router.post(
    "/estimate",
    response_model=EstimateResponse,
    summary="Estimate credit cost and validate a translation configuration",
)
def estimate(
    body: EstimateRequest,
    _current_user_id=Depends(get_current_user),
) -> EstimateResponse:
    """Return an estimated credit cost and validation result for a job configuration.

    Does not create a job. Safe to call multiple times as settings change.

    Returns 200 even when the config is invalid — the caller must check `is_valid`
    and display `validation_errors` before allowing submission.
    """
    errors: List[str] = []
    try:
        validate_job_config(
            mode=body.mode,
            target_language=body.target_language,
            translation_style=body.translation_style,
            user_level=body.user_level,
            explanation_depth=body.explanation_depth,
            source_language=body.source_language,
            quality_tier=body.quality_tier,
        )
    except ConfigValidationError as exc:
        errors = exc.errors

    estimated_credits = estimate_credits(
        word_count=max(0, body.word_count),
        mode=body.mode,
        explanation_depth=body.explanation_depth,
        quality_tier=body.quality_tier,
    )

    tier = get_language_pair_tier(
        source_language=body.source_language or "",
        target_language=body.target_language,
    )

    confidence_label: Optional[str] = None
    if body.source_language_confidence is not None:
        confidence_label = get_confidence_label(body.source_language_confidence)

    return EstimateResponse(
        estimated_credits=estimated_credits,
        language_pair_tier=tier,
        source_language_confidence_label=confidence_label,
        is_valid=len(errors) == 0,
        validation_errors=errors,
    )

class CreditsResponse(BaseModel):
    balance: int


class ProfileResponse(BaseModel):
    user_id: str
    email: str
    is_admin: bool
    balance: int


@router.get(
    "/profile",
    response_model=ProfileResponse,
    summary="Current user profile (email, admin flag, balance)",
)
def get_profile(
    current_user_id=Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ProfileResponse:
    user = session.get(User, current_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    acct = session.execute(
        select(UserCreditAccount).where(UserCreditAccount.user_id == current_user_id)
    ).scalar_one_or_none()
    bal = acct.balance if acct is not None else 0
    return ProfileResponse(
        user_id=str(user.user_id),
        email=user.email,
        is_admin=user.is_admin,
        balance=bal,
    )


@router.get(
    "/credits",
    response_model=CreditsResponse,
    summary="Get current user credit balance",
)
def get_credits(
    current_user_id=Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> CreditsResponse:
    """Return the authenticated user's current credit balance."""
    acct = session.execute(
        select(UserCreditAccount).where(UserCreditAccount.user_id == current_user_id)
    ).scalar_one_or_none()
    bal = acct.balance if acct is not None else 0
    return CreditsResponse(balance=bal)
