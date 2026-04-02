"""Tests for POST /config/estimate endpoint and updated job submission."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app as fastapi_app
from app.api.dependencies import get_current_user


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
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


@pytest.fixture()
def api_client(db_session):
    def override_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db_session] = override_db
    client = TestClient(fastapi_app, raise_server_exceptions=False)
    yield client, db_session
    fastapi_app.dependency_overrides.clear()


def _make_user(session) -> User:
    user = User(
        user_id=uuid.uuid4(),
        google_sub=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        is_admin=False,
    )
    session.add(user)
    account = UserCreditAccount(
        account_id=uuid.uuid4(),
        user_id=user.user_id,
        balance=10_000,
    )
    session.add(account)
    session.flush()
    return user


# ── POST /config/estimate ─────────────────────────────────────────────────────

def test_estimate_valid_translate(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/config/estimate", json={
        "word_count": 1000,
        "mode": "translate",
        "target_language": "en",
        "source_language": "ru",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is True
    assert body["estimated_credits"] == 10
    assert body["language_pair_tier"] == "standard"
    assert body["validation_errors"] == []
    assert body["source_language_confidence_label"] is None


def test_estimate_valid_guided_with_confidence(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/config/estimate", json={
        "word_count": 1000,
        "mode": "guided",
        "target_language": "de",
        "source_language": "fr",
        "translation_style": "literal",
        "user_level": "A2",
        "explanation_depth": "detailed",
        "source_language_confidence": 0.92,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is True
    assert body["estimated_credits"] == 23  # ceil(10 * 1.5 * 1.5)
    assert body["source_language_confidence_label"] == "high"


def test_estimate_invalid_config_returns_200_with_errors(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/config/estimate", json={
        "word_count": 1000,
        "mode": "bad_mode",
        "target_language": "xx",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_valid"] is False
    assert len(body["validation_errors"]) >= 2


def test_estimate_confidence_labels(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    for conf, expected_label in [(0.9, "high"), (0.7, "medium"), (0.3, "low")]:
        resp = client.post("/config/estimate", json={
            "word_count": 100,
            "mode": "translate",
            "target_language": "en",
            "translation_style": "natural",
            "user_level": "B1",
            "explanation_depth": "standard",
            "source_language_confidence": conf,
        })
        assert resp.json()["source_language_confidence_label"] == expected_label


# ── Updated POST /jobs — full config fields ───────────────────────────────────

def test_submit_job_with_full_config(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/jobs", json={
        "mode": "guided",
        "target_language": "en",
        "source_language_override": "ru",
        "translation_style": "literal",
        "user_level": "C1",
        "explanation_depth": "detailed",
        "word_count_estimate": 5000,
        "credit_estimate": 50,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["mode"] == "guided"
    assert body["translation_style"] == "literal"
    assert body["user_level"] == "C1"
    assert body["explanation_depth"] == "detailed"
    assert body["status"] == "queued"


def test_submit_job_translate_explanation_depth_not_stored(api_client) -> None:
    """In translate mode, explanation_depth is not persisted."""
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/jobs", json={
        "mode": "translate",
        "target_language": "de",
        "translation_style": "natural",
        "user_level": "B2",
        "explanation_depth": "detailed",
        "word_count_estimate": 1000,
        "credit_estimate": 10,
    })
    assert resp.status_code == 201
    # explanation_depth stored as None for translate mode
    assert resp.json()["explanation_depth"] is None


def test_submit_job_invalid_config_returns_422(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/jobs", json={
        "mode": "translate",
        "target_language": "xx",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
    })
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "errors" in detail["context"]


def test_submit_job_idempotency(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    csi = str(uuid.uuid4())
    payload = {
        "mode": "translate",
        "target_language": "en",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
        "word_count_estimate": 1000,
        "credit_estimate": 0,
        "client_submission_id": csi,
    }
    resp1 = client.post("/jobs", json=payload)
    assert resp1.status_code == 201
    job_id1 = resp1.json()["job_id"]

    # Second call with same client_submission_id → same job
    resp2 = client.post("/jobs", json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["job_id"] == job_id1


def test_submit_job_same_source_target_rejected(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    resp = client.post("/jobs", json={
        "mode": "translate",
        "target_language": "en",
        "source_language_override": "en",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
    })
    assert resp.status_code == 422


def test_submit_job_client_submission_id_stored(api_client) -> None:
    client, session = api_client
    user = _make_user(session)
    fastapi_app.dependency_overrides[get_current_user] = lambda: user.user_id

    csi = str(uuid.uuid4())
    resp = client.post("/jobs", json={
        "mode": "translate",
        "target_language": "fr",
        "translation_style": "natural",
        "user_level": "B1",
        "explanation_depth": "standard",
        "client_submission_id": csi,
    })
    assert resp.status_code == 201
    assert resp.json()["client_submission_id"] == csi
