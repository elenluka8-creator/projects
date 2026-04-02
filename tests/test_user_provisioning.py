from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db_session
from app.domain.services.user_service import (
    ExistingUser,
    IdentityClaims,
    ProvisioningResult,
    provision_user_with_store,
)
from app.main import app
from app.security.payload_guard import REDACTION_MARKER


class FakeUserStore:
    def __init__(self) -> None:
        self.by_google_sub: dict[str, ExistingUser] = {}
        self.create_calls = 0
        self.last_is_admin = False

    def find_by_google_sub(self, google_sub: str) -> ExistingUser | None:
        return self.by_google_sub.get(google_sub)

    def create_user_with_initial_credit(
        self,
        identity: IdentityClaims,
        initial_credit_grant: int,
        is_admin: bool,
    ) -> UUID:
        self.create_calls += 1
        self.last_is_admin = is_admin
        user_id = uuid4()
        self.by_google_sub[identity.google_sub] = ExistingUser(user_id=user_id)
        return user_id


def _token(secret: str, claims: dict[str, str], expires_seconds: int = 600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_provisioning_first_and_subsequent_login_emit_expected_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.domain.services.user_service.emit_event",
        lambda event_name, user_id: emitted.append((event_name, str(user_id))),
    )
    monkeypatch.setenv("INITIAL_CREDIT_GRANT", "100")
    store = FakeUserStore()
    identity = IdentityClaims(
        google_sub="google-sub-1",
        email="user@example.com",
        display_name="User One",
    )

    first = provision_user_with_store(store=store, identity=identity)
    second = provision_user_with_store(store=store, identity=identity)

    assert first.is_new_user is True
    assert second.is_new_user is False
    assert first.user_id == second.user_id
    assert store.create_calls == 1
    assert emitted[0][0] == "user_registered"
    assert emitted[1][0] == "user_signed_in"
    assert emitted[2][0] == "user_signed_in"
    assert store.last_is_admin is False


def test_provisioning_duplicate_first_login_is_idempotent_on_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.domain.services.user_service.emit_event",
        lambda event_name, user_id: emitted.append((event_name, str(user_id))),
    )

    expected_user_id = uuid4()

    class ConflictThenFindStore(FakeUserStore):
        def __init__(self) -> None:
            super().__init__()
            self.first_call = True
            self.by_google_sub["google-sub-2"] = ExistingUser(user_id=expected_user_id)

        def create_user_with_initial_credit(
            self,
            identity: IdentityClaims,
            initial_credit_grant: int,
            is_admin: bool,
        ) -> UUID:
            if self.first_call:
                self.first_call = False
                raise IntegrityError("insert", {}, Exception("duplicate"))
            return super().create_user_with_initial_credit(
                identity, initial_credit_grant, is_admin
            )

    store = ConflictThenFindStore()
    identity = IdentityClaims(
        google_sub="google-sub-2",
        email="user2@example.com",
        display_name="User Two",
    )

    result = provision_user_with_store(store=store, identity=identity)
    assert result.is_new_user is False
    assert result.user_id == expected_user_id
    assert emitted[-1][0] == "user_signed_in"


def test_auth_provision_endpoint_accepts_valid_nextauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXTAUTH_SECRET", "x" * 32)

    def fake_get_db_session():
        yield SimpleNamespace()

    monkeypatch.setattr(
        "app.api.routers.auth.provision_user",
        lambda session, identity: ProvisioningResult(
            user_id=uuid4(), is_new_user=True
        ),
    )
    app.dependency_overrides[get_db_session] = fake_get_db_session
    client = TestClient(app)

    token = _token(
        secret="x" * 32,
        claims={
            "google_sub": "google-sub-3",
            "email": "user3@example.com",
            "name": "User Three",
        },
    )
    response = client.post(
        "/auth/provision",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["is_new_user"] is True
    assert "user_id" in response.json()

    app.dependency_overrides.clear()


def test_auth_provision_endpoint_rejects_token_missing_required_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXTAUTH_SECRET", "x" * 32)
    client = TestClient(app)

    token = _token(
        secret="x" * 32,
        claims={"sub": "missing-google-sub-and-email"},
    )
    response = client.post(
        "/auth/provision",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["message"] == "Identity token missing required claims."
    assert detail["context"]["google_sub_present"] is False
    assert detail["context"]["email_present"] is False
    assert detail["context"].get("source_text", REDACTION_MARKER) == REDACTION_MARKER


def test_provisioning_marks_admin_when_email_in_admin_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com, second@example.com")
    monkeypatch.setattr("app.domain.services.user_service.emit_event", lambda *_: None)
    store = FakeUserStore()
    identity = IdentityClaims(
        google_sub="google-sub-admin",
        email="admin@example.com",
        display_name="Admin User",
    )

    result = provision_user_with_store(store=store, identity=identity)

    assert result.is_new_user is True
    assert store.last_is_admin is True


def test_analytics_failures_do_not_block_provisioning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INITIAL_CREDIT_GRANT", "100")
    store = FakeUserStore()
    identity = IdentityClaims(
        google_sub="google-sub-analytics-failure",
        email="user4@example.com",
        display_name="User Four",
    )

    def failing_emit_event(event_name: str, user_id: UUID) -> None:
        raise RuntimeError("analytics backend unavailable")

    monkeypatch.setattr(
        "app.domain.services.user_service.emit_event",
        failing_emit_event,
    )

    result = provision_user_with_store(store=store, identity=identity)

    assert result.is_new_user is True
    assert store.create_calls == 1


# ── Regression test: FIX-2 ───────────────────────────────────────────────────

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.user import CreditTransaction, User, UserCreditAccount
from app.domain.services.user_service import SqlAlchemyUserStore


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


def test_create_user_with_initial_credit_inserts_all_records(db_session):
    """FIX-2 regression: flush after user/account ensures no FK violation on commit."""
    store = SqlAlchemyUserStore(session=db_session)
    identity = IdentityClaims(
        google_sub="google-sub-fix2",
        email="fix2@example.com",
        display_name="Fix Two",
    )

    user_id = store.create_user_with_initial_credit(
        identity=identity,
        initial_credit_grant=50,
        is_admin=False,
    )

    # All three rows must be present after commit
    user = db_session.execute(select(User).where(User.user_id == user_id)).scalar_one()
    account = db_session.execute(
        select(UserCreditAccount).where(UserCreditAccount.user_id == user_id)
    ).scalar_one()
    tx = db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == user_id)
    ).scalar_one()

    assert user.email == "fix2@example.com"
    assert account.balance == 50
    assert tx.type == "grant"
    assert tx.amount == 50
    assert tx.balance_after == 50
