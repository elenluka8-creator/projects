"""Unit tests for the credit service — reserve, consume, refund, idempotency."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.user import User, UserCreditAccount
from app.domain.services.credit_service import (
    InsufficientCreditsError,
    consume_credits,
    refund_credits,
    reserve_credits,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


def _make_user_with_balance(session, balance: int = 500) -> tuple:
    user = User(google_sub=f"sub-{uuid.uuid4()}", email="u@example.com")
    session.add(user)
    session.flush()
    account = UserCreditAccount(user_id=user.user_id, balance=balance)
    session.add(account)
    session.flush()
    return user, account


def test_reserve_credits_deducts_balance(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    tx = reserve_credits(session, user.user_id, job_id, run_id, 200)

    assert tx.type == "reservation"
    assert tx.amount == -200
    assert account.balance == 300


def test_reserve_credits_raises_on_insufficient(session):
    user, _ = _make_user_with_balance(session, balance=50)
    with pytest.raises(InsufficientCreditsError) as exc_info:
        reserve_credits(session, user.user_id, uuid.uuid4(), uuid.uuid4(), 200)
    assert exc_info.value.required == 200
    assert exc_info.value.available == 50


def test_reserve_credits_idempotent(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    tx1 = reserve_credits(session, user.user_id, job_id, run_id, 100)
    tx2 = reserve_credits(session, user.user_id, job_id, run_id, 100)

    assert tx1.transaction_id == tx2.transaction_id
    assert account.balance == 400  # deducted only once


def test_consume_credits_creates_accounting_record(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    reserve_credits(session, user.user_id, job_id, run_id, 100)
    tx = consume_credits(session, user.user_id, job_id, run_id, 100)

    assert tx.type == "consumption"
    assert tx.amount == -100
    assert account.balance == 400  # balance unchanged by consume


def test_consume_credits_idempotent(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    reserve_credits(session, user.user_id, job_id, run_id, 100)
    tx1 = consume_credits(session, user.user_id, job_id, run_id, 100)
    tx2 = consume_credits(session, user.user_id, job_id, run_id, 100)

    assert tx1.transaction_id == tx2.transaction_id


def test_refund_credits_restores_balance(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    reserve_credits(session, user.user_id, job_id, run_id, 200)
    assert account.balance == 300

    tx = refund_credits(session, user.user_id, job_id, run_id, 200)

    assert tx.type == "refund"
    assert tx.amount == 200
    assert account.balance == 500


def test_refund_credits_idempotent(session):
    user, account = _make_user_with_balance(session, balance=500)
    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    reserve_credits(session, user.user_id, job_id, run_id, 100)
    tx1 = refund_credits(session, user.user_id, job_id, run_id, 100)
    tx2 = refund_credits(session, user.user_id, job_id, run_id, 100)

    assert tx1.transaction_id == tx2.transaction_id
    assert account.balance == 500  # refunded only once


def test_reserve_raises_on_missing_account(session):
    with pytest.raises(LookupError):
        reserve_credits(session, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 10)
