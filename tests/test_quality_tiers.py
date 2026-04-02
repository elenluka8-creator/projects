"""Tests for Translation Quality Tiers (FEAT-QUALITY-TIERS).

Covers:
- Policy constants and credit multiplier
- validate_job_config with quality_tier
- estimate endpoint with quality_tier
- Job submission stores quality_tier in DB
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — register all models
from app.config.policy import (
    TIER_CREDIT_MULTIPLIERS,
    TIER_MODELS,
    VALID_QUALITY_TIERS,
    ConfigValidationError,
    estimate_credits,
    get_tier_model,
    validate_job_config,
)
from app.db.base import Base
from app.db.models.user import User, UserCreditAccount
from app.db.session import get_db_session
from app.main import app
from app.api.routers.jobs import get_queue_broker
from app.queue.broker import InMemoryQueueBroker


# ---------------------------------------------------------------------------
# Policy unit tests
# ---------------------------------------------------------------------------

def test_valid_quality_tiers_constant():
    assert VALID_QUALITY_TIERS == {"express", "standard", "premium"}


def test_tier_credit_multipliers():
    assert float(TIER_CREDIT_MULTIPLIERS["express"]) == 0.5
    assert float(TIER_CREDIT_MULTIPLIERS["standard"]) == 1.0
    assert float(TIER_CREDIT_MULTIPLIERS["premium"]) == 2.5


def test_tier_models_all_present():
    for tier in VALID_QUALITY_TIERS:
        model = TIER_MODELS[tier]
        assert isinstance(model, str) and len(model) > 0


def test_get_tier_model_known():
    m = get_tier_model("express")
    assert m == TIER_MODELS["express"]


def test_get_tier_model_unknown_falls_back():
    m = get_tier_model("ultra")
    assert isinstance(m, str) and len(m) > 0


def test_estimate_credits_express_is_half_standard():
    standard = estimate_credits(1000, "translate", quality_tier="standard")
    express = estimate_credits(1000, "translate", quality_tier="express")
    assert express == max(1, round(standard * 0.5))


def test_estimate_credits_premium_is_2_5x_standard():
    standard = estimate_credits(1000, "translate", quality_tier="standard")
    premium = estimate_credits(1000, "translate", quality_tier="premium")
    import math
    assert premium == max(1, math.ceil(standard * 2.5))


def test_estimate_credits_default_tier_is_standard():
    no_tier = estimate_credits(500, "translate")
    with_standard = estimate_credits(500, "translate", quality_tier="standard")
    assert no_tier == with_standard


def test_validate_job_config_accepts_valid_tier():
    # Should not raise
    validate_job_config(
        mode="translate",
        target_language="ru",
        translation_style="natural",
        user_level="B1",
        explanation_depth="standard",
        quality_tier="premium",
    )


def test_validate_job_config_rejects_invalid_tier():
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_job_config(
            mode="translate",
            target_language="ru",
            translation_style="natural",
            user_level="B1",
            explanation_depth="standard",
            quality_tier="ultra",
        )
    assert "quality_tier" in str(exc_info.value).lower() or "ultra" in str(exc_info.value)


def test_validate_job_config_accepts_none_tier():
    # None means not specified — treated as standard; must not raise
    validate_job_config(
        mode="translate",
        target_language="de",
        translation_style="natural",
        user_level="B2",
        explanation_depth="standard",
        quality_tier=None,
    )


# ---------------------------------------------------------------------------
# API integration tests (estimate endpoint)
# ---------------------------------------------------------------------------

def _token(secret: str, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"user_id": user_id, "iat": int(now.timestamp()),
         "exp": int((now + timedelta(seconds=600)).timestamp())},
        secret, algorithm="HS256",
    )


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
    session = TestSession()
    broker = InMemoryQueueBroker()

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_queue_broker] = lambda: broker

    yield TestClient(app), session

    session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def _make_user(session, *, balance: int = 500) -> User:
    u = User(google_sub=f"sub-{uuid4()}", email=f"{uuid4()}@test.com")
    session.add(u)
    session.flush()
    acct = UserCreditAccount(user_id=u.user_id, balance=balance)
    session.add(acct)
    session.commit()
    return u


def test_estimate_endpoint_applies_tier_multiplier(client):
    http, session = client
    u = _make_user(session)
    token = _token("x" * 32, str(u.user_id))

    r_standard = http.post(
        "/config/estimate",
        headers={"Authorization": f"Bearer {token}"},
        json={"word_count": 1000, "mode": "translate", "target_language": "ru",
              "quality_tier": "standard"},
    )
    r_premium = http.post(
        "/config/estimate",
        headers={"Authorization": f"Bearer {token}"},
        json={"word_count": 1000, "mode": "translate", "target_language": "ru",
              "quality_tier": "premium"},
    )
    assert r_standard.status_code == 200
    assert r_premium.status_code == 200
    assert r_premium.json()["estimated_credits"] > r_standard.json()["estimated_credits"]


def test_estimate_endpoint_rejects_unknown_tier(client):
    http, session = client
    u = _make_user(session)
    token = _token("x" * 32, str(u.user_id))

    r = http.post(
        "/config/estimate",
        headers={"Authorization": f"Bearer {token}"},
        json={"word_count": 1000, "mode": "translate", "target_language": "ru",
              "quality_tier": "ultra"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_valid"] is False
    assert any("quality_tier" in e.lower() or "ultra" in e.lower()
               for e in data["validation_errors"])


def test_job_submission_stores_quality_tier(client):
    from app.db.models.artifact import Artifact

    http, session = client
    u = _make_user(session, balance=9999)
    token = _token("x" * 32, str(u.user_id))

    # Create a fake source artifact
    art = Artifact(
        user_id=u.user_id,
        job_id=uuid4(),
        artifact_type="source_epub",
        object_key="test/file.epub",
        storage_status="uploaded",
        size_bytes=1000,
        mime_type="application/epub+zip",
    )
    session.add(art)
    session.commit()

    r = http.post(
        "/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mode": "translate",
            "target_language": "de",
            "translation_style": "natural",
            "user_level": "B1",
            "explanation_depth": "standard",
            "quality_tier": "premium",
            "source_artifact_id": str(art.artifact_id),
            "credit_estimate": 10,
        },
    )
    assert r.status_code == 201
    job_id = r.json()["job_id"]

    from app.db.models.job import Job
    import uuid
    job = session.get(Job, uuid.UUID(job_id))
    assert job is not None
    assert job.quality_tier == "premium"


def test_job_submission_rejects_invalid_tier(client):
    from app.db.models.artifact import Artifact

    http, session = client
    u = _make_user(session, balance=9999)
    token = _token("x" * 32, str(u.user_id))

    art = Artifact(
        user_id=u.user_id,
        job_id=uuid4(),
        artifact_type="source_epub",
        object_key="test/file2.epub",
        storage_status="uploaded",
        size_bytes=1000,
        mime_type="application/epub+zip",
    )
    session.add(art)
    session.commit()

    r = http.post(
        "/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mode": "translate",
            "target_language": "de",
            "translation_style": "natural",
            "user_level": "B1",
            "explanation_depth": "standard",
            "quality_tier": "ultra",
            "source_artifact_id": str(art.artifact_id),
            "credit_estimate": 10,
        },
    )
    assert r.status_code == 422
