"""Integration tests for job API endpoints."""
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
    monkeypatch.setenv("SIGNED_URL_MIN_EXPIRY_SECONDS", "60")
    monkeypatch.setenv("SIGNED_URL_MAX_EXPIRY_SECONDS", "900")

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

    yield TestClient(app), test_session, broker

    test_session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def _make_user(session, balance: int = 1000):
    user = User(google_sub=f"sub-{uuid4()}", email="u@example.com")
    session.add(user)
    session.flush()
    account = UserCreditAccount(user_id=user.user_id, balance=balance)
    session.add(account)
    session.commit()
    return user


def test_create_job_returns_201(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "queued"
    assert data["mode"] == "translate"
    assert data["target_language"] == "de"
    assert broker.queue_length() == 1


def test_create_job_invalid_mode_returns_422(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    resp = http.post(
        "/jobs",
        json={"mode": "bad-mode", "target_language": "de"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_create_job_second_active_returns_409(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "fr", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_create_job_insufficient_credits_returns_402(client):
    http, session, broker = client
    user = _make_user(session, balance=10)
    token = _token("x" * 32, str(user.user_id))

    resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402


def test_list_jobs_returns_empty_initially(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    resp = http.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_jobs_returns_submitted_job(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = http.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 1
    assert jobs[0]["mode"] == "translate"


def test_get_job_detail_returns_job(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    create_resp = http.post(
        "/jobs",
        json={"mode": "guided", "target_language": "fr", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = create_resp.json()["job_id"]

    resp = http.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id
    assert resp.json()["mode"] == "guided"


def test_get_job_detail_not_found_returns_404(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    resp = http.get(f"/jobs/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_cancel_job_sets_cancel_requested(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    create_resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = create_resp.json()["job_id"]

    resp = http.post(f"/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["cancel_requested"] is True


def test_cancel_completed_job_returns_409(client):
    http, session, broker = client
    user = _make_user(session)
    token = _token("x" * 32, str(user.user_id))

    create_resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = create_resp.json()["job_id"]

    from app.db.models.job import Job
    import uuid
    job = session.get(Job, uuid.UUID(job_id))
    job.status = "completed"
    session.commit()

    resp = http.post(f"/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


def test_cancel_not_owned_job_returns_404(client):
    http, session, broker = client
    user = _make_user(session)
    other_user = _make_user(session)
    token_other = _token("x" * 32, str(other_user.user_id))

    create_resp = http.post(
        "/jobs",
        json={"mode": "translate", "target_language": "de", "credit_estimate": 0},
        headers={"Authorization": f"Bearer {_token('x' * 32, str(user.user_id))}"},
    )
    job_id = create_resp.json()["job_id"]

    resp = http.post(f"/jobs/{job_id}/cancel", headers={"Authorization": f"Bearer {token_other}"})
    assert resp.status_code == 404


def test_unauthenticated_request_returns_401(client):
    http, session, broker = client
    resp = http.get("/jobs")
    assert resp.status_code == 401
