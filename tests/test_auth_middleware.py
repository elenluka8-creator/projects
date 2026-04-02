from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, status

from app.api.dependencies import get_current_user, require_admin


def _make_token(secret: str, user_id: str, expires_in_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_get_current_user_valid_jwt_returns_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret"
    monkeypatch.setenv("NEXTAUTH_SECRET", secret)
    user_id = str(uuid4())
    token = _make_token(secret=secret, user_id=user_id, expires_in_seconds=600)

    resolved = get_current_user(authorization=f"Bearer {token}")

    assert str(resolved) == user_id


def test_get_current_user_missing_header_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXTAUTH_SECRET", "test-secret")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_expired_jwt_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret"
    monkeypatch.setenv("NEXTAUTH_SECRET", secret)
    token = _make_token(secret=secret, user_id=str(uuid4()), expires_in_seconds=-60)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=f"Bearer {token}")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_invalid_signature_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXTAUTH_SECRET", "expected-secret")
    token = _make_token(
        secret="different-secret",
        user_id=str(uuid4()),
        expires_in_seconds=600,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=f"Bearer {token}")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_malformed_token_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXTAUTH_SECRET", "test-secret")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization="Bearer not-a-jwt")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_require_admin_allows_admin_user() -> None:
    user_id = uuid4()
    session = SimpleNamespace(get=lambda model, pk: SimpleNamespace(is_admin=True))

    resolved = require_admin(current_user_id=user_id, session=session)

    assert resolved == user_id


def test_require_admin_rejects_non_admin_user() -> None:
    session = SimpleNamespace(get=lambda model, pk: SimpleNamespace(is_admin=False))

    with pytest.raises(HTTPException) as exc_info:
        require_admin(current_user_id=uuid4(), session=session)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
