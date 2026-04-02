"""Credit service for job lifecycle credit operations.

Operations:
  reserve_credits  — deduct balance at job submission; creates reservation transaction
  consume_credits  — record consumption at job completion (no balance change)
  refund_credits   — restore balance on failure or cancellation

All three operations are idempotent per job_run_id to support safe retries.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import CreditTransaction, UserCreditAccount
from app.logging.structured import log_structured

logger = logging.getLogger(__name__)

TRANSACTION_TYPES = frozenset(
    {"grant", "reservation", "consumption", "refund", "admin_adjustment"}
)


class InsufficientCreditsError(Exception):
    """Raised when a user's credit balance is insufficient for a reservation."""

    def __init__(self, user_id: uuid.UUID, required: int, available: int) -> None:
        super().__init__(
            f"Insufficient credits for user {user_id}: required={required}, available={available}"
        )
        self.user_id = user_id
        self.required = required
        self.available = available


def reserve_credits(
    session: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    job_run_id: uuid.UUID,
    amount: int,
) -> CreditTransaction:
    """Reserve credits at job submission by deducting from the user balance.

    Idempotent: if a reservation already exists for this job_id + user_id,
    returns the existing transaction without double-deducting.

    Raises:
        InsufficientCreditsError: if balance < amount.
        LookupError: if credit account does not exist.
    """
    existing = _find_existing(session, user_id=user_id, job_id=job_id, tx_type="reservation")
    if existing is not None:
        return existing

    account = _get_account(session, user_id)
    if account.balance < amount:
        raise InsufficientCreditsError(
            user_id=user_id, required=amount, available=account.balance
        )

    account.balance -= amount
    balance_after = account.balance

    tx = CreditTransaction(
        user_id=user_id,
        job_id=job_id,
        job_run_id=job_run_id,
        type="reservation",
        amount=-amount,
        balance_after=balance_after,
    )
    session.add(tx)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="credits_reserved",
        payload={
            "user_id": str(user_id),
            "job_id": str(job_id),
            "job_run_id": str(job_run_id),
            "amount": amount,
            "balance_after": balance_after,
        },
    )
    return tx


def consume_credits(
    session: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    job_run_id: uuid.UUID,
    amount: int,
) -> CreditTransaction:
    """Record credit consumption at job completion.

    The balance was already deducted by reserve_credits; this is an accounting
    record only — no further balance change.

    Idempotent: if a consumption already exists for this job_run_id, returns it.
    """
    existing = _find_existing(session, user_id=user_id, job_run_id=job_run_id, tx_type="consumption")
    if existing is not None:
        return existing

    account = _get_account(session, user_id)
    tx = CreditTransaction(
        user_id=user_id,
        job_id=job_id,
        job_run_id=job_run_id,
        type="consumption",
        amount=-amount,
        balance_after=account.balance,
    )
    session.add(tx)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="credits_consumed",
        payload={
            "user_id": str(user_id),
            "job_id": str(job_id),
            "job_run_id": str(job_run_id),
            "amount": amount,
        },
    )
    return tx


def refund_credits(
    session: Session,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    job_run_id: uuid.UUID,
    amount: int,
) -> CreditTransaction:
    """Refund reserved credits on failure or cancellation.

    Restores the deducted balance and creates a refund transaction record.

    Idempotent: if a refund already exists for this job_run_id, returns it
    without double-crediting.
    """
    existing = _find_existing(session, user_id=user_id, job_run_id=job_run_id, tx_type="refund")
    if existing is not None:
        return existing

    account = _get_account(session, user_id)
    account.balance += amount
    balance_after = account.balance

    tx = CreditTransaction(
        user_id=user_id,
        job_id=job_id,
        job_run_id=job_run_id,
        type="refund",
        amount=amount,
        balance_after=balance_after,
    )
    session.add(tx)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="credits_refunded",
        payload={
            "user_id": str(user_id),
            "job_id": str(job_id),
            "job_run_id": str(job_run_id),
            "amount": amount,
            "balance_after": balance_after,
        },
    )
    return tx


def _get_account(session: Session, user_id: uuid.UUID) -> UserCreditAccount:
    account = session.execute(
        select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
    ).scalar_one_or_none()
    if account is None:
        raise LookupError(f"Credit account not found for user {user_id}")
    return account


def _find_existing(
    session: Session,
    user_id: uuid.UUID,
    tx_type: str,
    job_id: Optional[uuid.UUID] = None,
    job_run_id: Optional[uuid.UUID] = None,
) -> Optional[CreditTransaction]:
    stmt = select(CreditTransaction).where(
        CreditTransaction.user_id == user_id,
        CreditTransaction.type == tx_type,
    )
    if job_id is not None:
        stmt = stmt.where(CreditTransaction.job_id == job_id)
    if job_run_id is not None:
        stmt = stmt.where(CreditTransaction.job_run_id == job_run_id)
    return session.execute(stmt).scalar_one_or_none()


def admin_adjust_balance(
    session: Session,
    *,
    target_user_id: uuid.UUID,
    delta: int,
    admin_user_id: uuid.UUID,
) -> CreditTransaction:
    """Apply a signed balance change for a user (admin grant or adjustment).

    Creates a transaction of type ``admin_adjustment``. ``delta`` may be
    negative; the resulting balance must remain non-negative.

    Raises:
        ValueError: if delta is zero or would make balance negative.
        LookupError: if the target has no credit account.
    """
    if delta == 0:
        raise ValueError("delta must be non-zero")

    account = _get_account(session, target_user_id)
    new_balance = account.balance + delta
    if new_balance < 0:
        raise ValueError("adjustment would make balance negative")

    account.balance = new_balance
    tx = CreditTransaction(
        user_id=target_user_id,
        job_id=None,
        job_run_id=None,
        type="admin_adjustment",
        amount=delta,
        balance_after=new_balance,
    )
    session.add(tx)
    session.flush()

    log_structured(
        logger=logger,
        level=logging.INFO,
        message="admin_credits_adjusted",
        payload={
            "target_user_id": str(target_user_id),
            "admin_user_id": str(admin_user_id),
            "delta": delta,
            "balance_after": new_balance,
        },
    )
    return tx
