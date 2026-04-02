from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401 — ensures all models are registered with Base
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.storage.client import FakeStorageClient, get_storage_client


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

    def override_db():
        yield test_session

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_storage_client] = lambda: FakeStorageClient()

    yield TestClient(app), test_session

    test_session.close()
    engine.dispose()
    app.dependency_overrides.clear()


def test_post_artifacts_returns_upload_url(client) -> None:
    http_client, _ = client
    user_id = uuid4()
    job_id = uuid4()
    token = _token("x" * 32, str(user_id))

    response = http_client.post(
        "/storage/artifacts",
        json={
            "artifact_type": "source_epub",
            "job_id": str(job_id),
            "size_bytes": 204800,
            "expires_in_seconds": 300,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "artifact_id" in data
    assert "upload_url" in data
    assert "object_key" in data
    assert str(user_id) in data["object_key"]
    assert str(job_id) in data["object_key"]
    assert "source_epub" in data["object_key"]
    assert "upload" in data["upload_url"]


def test_post_artifacts_rejects_invalid_artifact_type(client) -> None:
    http_client, _ = client
    user_id = uuid4()
    token = _token("x" * 32, str(user_id))

    response = http_client.post(
        "/storage/artifacts",
        json={
            "artifact_type": "invalid_type",
            "job_id": str(uuid4()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Invalid artifact_type" in response.json()["detail"]["message"]


def test_post_artifacts_rejects_expiry_out_of_bounds(client) -> None:
    http_client, _ = client
    user_id = uuid4()
    token = _token("x" * 32, str(user_id))

    response = http_client.post(
        "/storage/artifacts",
        json={
            "artifact_type": "output_epub",
            "job_id": str(uuid4()),
            "expires_in_seconds": 9999,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "message" in detail


def test_post_artifacts_requires_auth(client) -> None:
    http_client, _ = client
    response = http_client.post(
        "/storage/artifacts",
        json={"artifact_type": "source_epub", "job_id": str(uuid4())},
    )
    assert response.status_code == 401


def test_get_download_url_returns_url_for_owner(client) -> None:
    from app.db.models.artifact import Artifact

    http_client, session = client
    user_id = uuid4()
    job_id = uuid4()
    artifact_id = uuid4()
    object_key = f"users/{user_id}/jobs/{job_id}/output_epub/{artifact_id}"

    artifact = Artifact(
        artifact_id=artifact_id,
        user_id=user_id,
        job_id=job_id,
        artifact_type="output_epub",
        object_key=object_key,
        size_bytes=None,
        storage_status="active",
    )
    session.add(artifact)
    session.commit()

    token = _token("x" * 32, str(user_id))
    response = http_client.get(
        f"/storage/artifacts/{artifact_id}/download-url",
        params={"expires_in_seconds": 300},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["artifact_id"] == str(artifact_id)
    assert "download" in data["download_url"]
    assert data["object_key"] == object_key


def test_get_download_url_denies_cross_user(client) -> None:
    from app.db.models.artifact import Artifact

    http_client, session = client
    owner_id = uuid4()
    other_user_id = uuid4()
    artifact_id = uuid4()

    artifact = Artifact(
        artifact_id=artifact_id,
        user_id=owner_id,
        job_id=uuid4(),
        artifact_type="source_epub",
        object_key=f"users/{owner_id}/jobs/{uuid4()}/source_epub/{artifact_id}",
        storage_status="active",
    )
    session.add(artifact)
    session.commit()

    token = _token("x" * 32, str(other_user_id))
    response = http_client.get(
        f"/storage/artifacts/{artifact_id}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Forbidden."


def test_get_download_url_returns_404_for_unknown_artifact(client) -> None:
    http_client, _ = client
    user_id = uuid4()
    token = _token("x" * 32, str(user_id))

    response = http_client.get(
        f"/storage/artifacts/{uuid4()}/download-url",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Artifact not found."


def test_get_download_url_rejects_expiry_out_of_bounds(client) -> None:
    from app.db.models.artifact import Artifact

    http_client, session = client
    user_id = uuid4()
    artifact_id = uuid4()

    artifact = Artifact(
        artifact_id=artifact_id,
        user_id=user_id,
        job_id=uuid4(),
        artifact_type="output_epub",
        object_key=f"users/{user_id}/jobs/{uuid4()}/output_epub/{artifact_id}",
        storage_status="active",
    )
    session.add(artifact)
    session.commit()

    token = _token("x" * 32, str(user_id))
    response = http_client.get(
        f"/storage/artifacts/{artifact_id}/download-url",
        params={"expires_in_seconds": 9999},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "message" in response.json()["detail"]
