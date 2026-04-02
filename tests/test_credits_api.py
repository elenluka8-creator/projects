from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.user import CreditTransaction, User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app


def _token(secret: str, user_id: str, expires_seconds: int = 600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXTAUTH_SECRET", "x" * 32)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    test_session = TestSession()

    def override_db():
        yield test_session

    app.dependency_overrides[get_db_session] = override_db

    yield TestClient(app), test_session

    test_session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def _seed_user(session, user_id, balance: int = 100) -> None:
    session.add(
        User(
            user_id=user_id,
            google_sub=f"sub-{user_id}",
            email=f"{user_id}@example.com",
        )
    )
    session.add(
        UserCreditAccount(
            account_id=uuid4(),
            user_id=user_id,
            balance=balance,
        )
    )


def test_credit_history_returns_transactions(client) -> None:
    tc, session = client
    uid = uuid4()
    job_id = uuid4()
    _seed_user(session, uid, balance=30)
    tx_id = uuid4()
    session.add(
        CreditTransaction(
            transaction_id=tx_id,
            user_id=uid,
            job_id=job_id,
            job_run_id=None,
            type="grant",
            amount=100,
            balance_after=100,
        )
    )
    session.commit()

    secret = "x" * 32
    res = tc.get(
        "/credits/history",
        headers={"Authorization": f"Bearer {_token(secret, str(uid))}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    row = data[0]
    assert row["transaction_id"] == str(tx_id)
    assert row["type"] == "grant"
    assert row["amount"] == 100
    assert row["balance_after"] == 100
    assert row["job_id"] == str(job_id)
    assert "created_at" in row


def test_credit_history_empty(client) -> None:
    tc, session = client
    uid = uuid4()
    _seed_user(session, uid, balance=0)
    session.commit()

    secret = "x" * 32
    res = tc.get(
        "/credits/history",
        headers={"Authorization": f"Bearer {_token(secret, str(uid))}"},
    )
    assert res.status_code == 200
    assert res.json() == []


def test_credit_history_unauthorized(client) -> None:
    tc, _ = client
    res = tc.get("/credits/history")
    assert res.status_code == 401
