from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import InMemoryOwnershipStore, get_ownership_store
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
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NEXTAUTH_SECRET", "x" * 32)
    return TestClient(app)


def test_job_access_allowed_for_owner(client: TestClient) -> None:
    owner_id = uuid4()
    job_id = uuid4()

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(job_owners={job_id: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    response = client.get(
        f"/security/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == str(job_id)
    app.dependency_overrides.clear()


def test_job_access_denied_for_cross_user(client: TestClient) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    job_id = uuid4()

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(job_owners={job_id: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(other_user_id))

    response = client.get(
        f"/security/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Forbidden."
    app.dependency_overrides.clear()


def test_artifact_access_allowed_for_owner(client: TestClient) -> None:
    owner_id = uuid4()
    artifact_id = uuid4()

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(artifact_owners={artifact_id: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    response = client.get(
        f"/security/artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["artifact_id"] == str(artifact_id)
    app.dependency_overrides.clear()


def test_artifact_access_denied_for_cross_user(client: TestClient) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    artifact_id = uuid4()

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(artifact_owners={artifact_id: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(other_user_id))

    response = client.get(
        f"/security/artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Forbidden."
    app.dependency_overrides.clear()
