"""Tests for FEAT-ADMIN API routes."""
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
from app.db.models.job import Job
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app
from app.api.routers.jobs import get_queue_broker
from app.queue.broker import InMemoryQueueBroker


def _token(secret: str, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=600)).timestamp()),
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
    broker = InMemoryQueueBroker()

    def override_db():
        yield test_session

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_queue_broker] = lambda: broker

    yield TestClient(app), test_session

    test_session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def _make_user(session, *, admin: bool = False, balance: int = 100):
    u = User(google_sub=f"sub-{uuid4()}", email=f"{uuid4()}@example.com", is_admin=admin)
    session.add(u)
    session.flush()
    acct = UserCreditAccount(user_id=u.user_id, balance=balance)
    session.add(acct)
    session.commit()
    return u


def test_admin_list_users_requires_admin(client):
    http, session = client
    u = _make_user(session, admin=False)
    token = _token("x" * 32, str(u.user_id))
    r = http.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_adjust_credits_and_list_jobs(client):
    http, session = client
    admin = _make_user(session, admin=True, balance=50)
    target = _make_user(session, admin=False, balance=10)
    job = Job(
        user_id=target.user_id,
        status="queued",
        mode="translate",
        target_language="de",
    )
    session.add(job)
    session.commit()

    token = _token("x" * 32, str(admin.user_id))

    r = http.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 2
    emails = {row["email"] for row in users}
    assert admin.email in emails and target.email in emails

    r2 = http.post(
        f"/admin/users/{target.user_id}/credits",
        headers={"Authorization": f"Bearer {token}"},
        json={"delta": 40},
    )
    assert r2.status_code == 200
    assert r2.json()["balance_after"] == 50

    r3 = http.get("/admin/jobs", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 200
    jobs = r3.json()
    assert len(jobs) == 1
    assert jobs[0]["user_email"] == target.email
    assert jobs[0]["mode"] == "translate"


def test_non_admin_cannot_adjust(client):
    http, session = client
    u = _make_user(session, admin=False)
    other = _make_user(session, admin=False, balance=5)
    token = _token("x" * 32, str(u.user_id))
    r = http.post(
        f"/admin/users/{other.user_id}/credits",
        headers={"Authorization": f"Bearer {token}"},
        json={"delta": 10},
    )
    assert r.status_code == 403


def test_admin_settings_get_and_patch(client):
    http, session = client
    admin = _make_user(session, admin=True)
    token = _token("x" * 32, str(admin.user_id))

    r = http.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "initial_credit_grant" in data
    assert isinstance(data["initial_credit_grant"], int)

    r2 = http.patch(
        "/admin/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"initial_credit_grant": 250},
    )
    assert r2.status_code == 200
    assert r2.json()["initial_credit_grant"] == 250

    r3 = http.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})
    assert r3.json()["initial_credit_grant"] == 250


def test_admin_settings_non_admin_forbidden(client):
    http, session = client
    u = _make_user(session, admin=False)
    token = _token("x" * 32, str(u.user_id))
    r = http.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_config_profile_returns_is_admin(client):
    http, session = client
    u = _make_user(session, admin=True, balance=42)
    token = _token("x" * 32, str(u.user_id))
    r = http.get("/config/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["is_admin"] is True
    assert data["balance"] == 42
