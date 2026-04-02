"""Credits router — credit transaction history."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import CreditTransaction
from app.db.session import get_db_session

router = APIRouter(prefix="/credits", tags=["credits"])


class CreditHistoryRow(BaseModel):
    transaction_id: str
    type: str
    amount: int
    balance_after: int = Field(description="Account balance after this transaction.")
    created_at: str
    job_id: Optional[str] = None


@router.get("/history", response_model=list[CreditHistoryRow])
def credit_history(
    current_user_id: uuid.UUID = Depends(get_current_user),
    session: Session = Depends(get_db_session),
    limit: int = Query(200, ge=1, le=500),
) -> list[CreditHistoryRow]:
    """Return the current user's credit transaction history, newest first."""
    rows = (
        session.execute(
            select(CreditTransaction)
            .where(CreditTransaction.user_id == current_user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        CreditHistoryRow(
            transaction_id=str(r.transaction_id),
            type=r.type,
            amount=r.amount,
            balance_after=r.balance_after,
            created_at=r.created_at.isoformat(),
            job_id=str(r.job_id) if r.job_id is not None else None,
        )
        for r in rows
    ]
