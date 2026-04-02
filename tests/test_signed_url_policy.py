from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import InMemoryOwnershipStore, get_ownership_store
from app.main import app
from app.security.signed_url_policy import issue_signed_url, validate_signed_url_purpose


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
    monkeypatch.setenv("SIGNED_URL_MIN_EXPIRY_SECONDS", "60")
    monkeypatch.setenv("SIGNED_URL_MAX_EXPIRY_SECONDS", "900")
    return TestClient(app)


def test_create_signed_url_allows_owned_object(client: TestClient) -> None:
    owner_id = uuid4()
    object_key = "books/u1/ch1.epub"

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(object_owners={object_key: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    response = client.post(
        "/security/signed-urls",
        params={
            "object_key": object_key,
            "purpose": "upload",
            "expires_in_seconds": 300,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["purpose"] == "upload"
    assert body["object_key"] == object_key
    assert "purpose=upload" in body["signed_url"]
    app.dependency_overrides.clear()


def test_create_signed_url_denies_cross_user(client: TestClient) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    object_key = "books/u1/ch2.epub"

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(object_owners={object_key: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(other_user_id))

    response = client.post(
        "/security/signed-urls",
        params={"object_key": object_key, "purpose": "download"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Forbidden."
    app.dependency_overrides.clear()


def test_create_signed_url_enforces_expiry_bounds(client: TestClient) -> None:
    owner_id = uuid4()
    object_key = "books/u1/ch3.epub"

    def fake_store() -> InMemoryOwnershipStore:
        return InMemoryOwnershipStore(object_owners={object_key: owner_id})

    app.dependency_overrides[get_ownership_store] = fake_store
    token = _token("x" * 32, str(owner_id))

    response = client.post(
        "/security/signed-urls",
        params={
            "object_key": object_key,
            "purpose": "download",
            "expires_in_seconds": 9999,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Signed URL policy violation."
    app.dependency_overrides.clear()


def test_signed_url_purpose_cannot_be_reused_for_other_direction() -> None:
    url = issue_signed_url(
        object_key="books/u2/ch1.epub",
        purpose="upload",
        expires_in_seconds=120,
    )

    assert validate_signed_url_purpose(url, "upload") is True
    assert validate_signed_url_purpose(url, "download") is False
