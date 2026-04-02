"""Admin API — user credit management and cross-user job visibility (FEAT-ADMIN).

All routes require ``is_admin`` on the authenticated user.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_db_session, require_admin
from app.api.errors import build_safe_error_detail
from app.db.models.app_setting import AppSetting
from app.db.models.cost_ledger import CostLedgerEntry
from app.db.models.job import Job, JobRun
from app.db.models.translation_batch import TranslationBatch
from app.db.models.user import User
from app.domain.services.credit_service import admin_adjust_balance
from app.security.audit_log import AUDIT_ADMIN_CREDIT_ADJUST, emit_audit_event

router = APIRouter(prefix="/admin", tags=["admin"])

_MAX_JOBS = 500


class AdminUserRow(BaseModel):
    user_id: str
    email: str
    display_name: Optional[str]
    is_admin: bool
    balance: int
    created_at: str


class AdminJobRow(BaseModel):
    job_id: str
    user_id: str
    user_email: str
    status: str
    mode: str
    target_language: str
    source_language_override: Optional[str]
    translation_style: Optional[str]
    user_level: Optional[str]
    explanation_depth: Optional[str]
    quality_tier: Optional[str]
    word_count_estimate: Optional[int]
    credit_estimate: Optional[int]
    created_at: str
    updated_at: str
    progress_percent: int
    pipeline_stage: Optional[str]
    failure_class: Optional[str]


class AdminJobRunInfo(BaseModel):
    job_run_id: str
    run_status: str
    worker_id: Optional[str]
    heartbeat_at: Optional[str]
    lease_expires_at: Optional[str]
    completed_batches: int
    total_batches: int


class AdminJobDetail(BaseModel):
    job_id: str
    user_id: str
    user_email: str
    status: str
    mode: str
    target_language: str
    source_language_override: Optional[str]
    translation_style: Optional[str]
    user_level: Optional[str]
    explanation_depth: Optional[str]
    quality_tier: Optional[str]
    word_count_estimate: Optional[int]
    credit_estimate: Optional[int]
    failure_reason: Optional[str]
    failure_class: Optional[str]
    created_at: str
    updated_at: str
    processing_started_at: Optional[str]
    progress_percent: int
    pipeline_stage: Optional[str]
    total_cost_usd: float
    total_tokens_in: int
    total_tokens_out: int
    run_info: Optional[AdminJobRunInfo]


class AppSettingsResponse(BaseModel):
    initial_credit_grant: int


class AppSettingsPatchRequest(BaseModel):
    initial_credit_grant: int = Field(..., ge=0, description="Credits granted to every new user on sign-up.")


class CreditAdjustRequest(BaseModel):
    delta: int = Field(..., description="Credits to add (positive) or remove (negative).")


class CreditAdjustResponse(BaseModel):
    user_id: str
    balance_after: int
    transaction_id: str


@router.get("/users", response_model=List[AdminUserRow])
def list_users(
    _admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> List[AdminUserRow]:
    """List all users with current credit balances."""
    users = (
        session.execute(
            select(User).options(joinedload(User.credit_account)).order_by(User.created_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    rows: List[AdminUserRow] = []
    for u in users:
        bal = u.credit_account.balance if u.credit_account is not None else 0
        rows.append(
            AdminUserRow(
                user_id=str(u.user_id),
                email=u.email,
                display_name=u.display_name,
                is_admin=u.is_admin,
                balance=bal,
                created_at=u.created_at.isoformat(),
            )
        )
    return rows


@router.post(
    "/users/{user_id}/credits",
    response_model=CreditAdjustResponse,
    status_code=status.HTTP_200_OK,
)
def adjust_user_credits(
    user_id: uuid.UUID,
    body: CreditAdjustRequest,
    admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> CreditAdjustResponse:
    """Add or subtract credits for a user (admin adjustment)."""
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="User not found.",
                context={"user_id": str(user_id)},
            ),
        )

    try:
        tx = admin_adjust_balance(
            session,
            target_user_id=user_id,
            delta=body.delta,
            admin_user_id=admin_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_safe_error_detail(
                message=str(exc),
                context={"user_id": str(user_id)},
            ),
        ) from exc
    except LookupError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Credit account not found for user.",
                context={"user_id": str(user_id)},
            ),
        ) from None

    emit_audit_event(
        AUDIT_ADMIN_CREDIT_ADJUST,
        actor_id=admin_id,
        target=f"user:{user_id}",
        extra={"delta": body.delta, "balance_after": tx.balance_after},
    )

    return CreditAdjustResponse(
        user_id=str(user_id),
        balance_after=tx.balance_after,
        transaction_id=str(tx.transaction_id),
    )


@router.get("/jobs", response_model=List[AdminJobRow])
def list_all_jobs(
    _admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> List[AdminJobRow]:
    """List recent jobs across all users (metadata only)."""
    q = (
        select(Job, User.email)
        .join(User, Job.user_id == User.user_id)
        .order_by(Job.created_at.desc())
        .limit(_MAX_JOBS)
    )
    result = session.execute(q).all()
    out: List[AdminJobRow] = []
    for job, email in result:
        out.append(
            AdminJobRow(
                job_id=str(job.job_id),
                user_id=str(job.user_id),
                user_email=email,
                status=job.status,
                mode=job.mode,
                target_language=job.target_language,
                source_language_override=job.source_language_override,
                translation_style=job.translation_style,
                user_level=job.user_level,
                explanation_depth=job.explanation_depth,
                quality_tier=job.quality_tier,
                word_count_estimate=job.word_count_estimate,
                credit_estimate=job.credit_estimate,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                progress_percent=job.progress_percent,
                pipeline_stage=job.pipeline_stage,
                failure_class=job.failure_class,
            )
        )
    return out


@router.get("/jobs/{job_id}", response_model=AdminJobDetail)
def get_job_detail(
    job_id: uuid.UUID,
    _admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> AdminJobDetail:
    """Return full details and aggregated cost for a single job."""
    q = (
        select(Job, User.email)
        .join(User, Job.user_id == User.user_id)
        .where(Job.job_id == job_id)
    )
    row = session.execute(q).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_safe_error_detail(
                message="Job not found.",
                context={"job_id": str(job_id)},
            ),
        )
    job, email = row

    cost_q = select(
        func.coalesce(func.sum(CostLedgerEntry.estimated_cost_usd), 0.0).label("total_cost_usd"),
        func.coalesce(func.sum(CostLedgerEntry.tokens_in), 0).label("total_tokens_in"),
        func.coalesce(func.sum(CostLedgerEntry.tokens_out), 0).label("total_tokens_out"),
    ).where(CostLedgerEntry.job_id == job_id)
    cost_row = session.execute(cost_q).one()

    run_info: Optional[AdminJobRunInfo] = None
    if job.current_run_id is not None:
        run = session.get(JobRun, job.current_run_id)
        if run is not None:
            batch_q = select(
                func.count(TranslationBatch.batch_id).label("total"),
                func.coalesce(
                    func.sum(
                        func.cast(TranslationBatch.status == "completed", Integer)
                    ),
                    0,
                ).label("completed"),
            ).where(TranslationBatch.job_run_id == run.job_run_id)
            batch_row = session.execute(batch_q).one()
            run_info = AdminJobRunInfo(
                job_run_id=str(run.job_run_id),
                run_status=run.status,
                worker_id=run.worker_id,
                heartbeat_at=run.heartbeat_at.isoformat() if run.heartbeat_at else None,
                lease_expires_at=run.lease_expires_at.isoformat() if run.lease_expires_at else None,
                completed_batches=int(batch_row.completed),
                total_batches=int(batch_row.total),
            )

    return AdminJobDetail(
        job_id=str(job.job_id),
        user_id=str(job.user_id),
        user_email=email,
        status=job.status,
        mode=job.mode,
        target_language=job.target_language,
        source_language_override=job.source_language_override,
        translation_style=job.translation_style,
        user_level=job.user_level,
        explanation_depth=job.explanation_depth,
        quality_tier=job.quality_tier,
        word_count_estimate=job.word_count_estimate,
        credit_estimate=job.credit_estimate,
        failure_reason=job.failure_reason,
        failure_class=job.failure_class,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        processing_started_at=job.processing_started_at.isoformat() if job.processing_started_at else None,
        progress_percent=job.progress_percent,
        pipeline_stage=job.pipeline_stage,
        total_cost_usd=float(cost_row.total_cost_usd),
        total_tokens_in=int(cost_row.total_tokens_in),
        total_tokens_out=int(cost_row.total_tokens_out),
        run_info=run_info,
    )


_SETTINGS_KEY = "initial_credit_grant"
_SETTINGS_DEFAULT = 0


@router.get("/settings", response_model=AppSettingsResponse)
def get_settings(
    _admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> AppSettingsResponse:
    """Return current application settings."""
    row = session.get(AppSetting, _SETTINGS_KEY)
    value = int(row.value) if row is not None else _SETTINGS_DEFAULT
    return AppSettingsResponse(initial_credit_grant=value)


@router.patch("/settings", response_model=AppSettingsResponse)
def update_settings(
    body: AppSettingsPatchRequest,
    _admin_id: uuid.UUID = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> AppSettingsResponse:
    """Update application settings."""
    row = session.get(AppSetting, _SETTINGS_KEY)
    if row is None:
        row = AppSetting(key=_SETTINGS_KEY, value=str(body.initial_credit_grant))
        session.add(row)
    else:
        row.value = str(body.initial_credit_grant)
    session.commit()
    return AppSettingsResponse(initial_credit_grant=int(row.value))
