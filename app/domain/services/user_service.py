from __future__ import annotations

import os
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics.events import AuthEventName, emit_event
from app.db.models.app_setting import AppSetting
from app.db.models.user import CreditTransaction, User, UserCreditAccount
from app.logging.structured import log_structured

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityClaims:
    google_sub: str
    email: str
    display_name: str | None


@dataclass(frozen=True)
class ProvisioningResult:
    user_id: uuid.UUID
    is_new_user: bool


@dataclass(frozen=True)
class ExistingUser:
    user_id: uuid.UUID


def _initial_credit_grant(session: Session | None = None) -> int:
    """Return the initial credit grant for new users.

    Checks the app_settings table first (key='initial_credit_grant'), then
    falls back to the INITIAL_CREDIT_GRANT env var, then to 0.
    """
    if session is not None:
        try:
            row = session.get(AppSetting, "initial_credit_grant")
            if row is not None:
                return int(row.value)
        except Exception:
            pass
    value = os.getenv("INITIAL_CREDIT_GRANT", "0")
    try:
        return int(value)
    except ValueError:
        return 0


def _is_admin_email(email: str) -> bool:
    configured = os.getenv("ADMIN_EMAILS", "")
    if not configured.strip():
        return False
    admin_emails = {item.strip().lower() for item in configured.split(",") if item.strip()}
    return email.strip().lower() in admin_emails


class UserStore(Protocol):
    def find_by_google_sub(self, google_sub: str) -> ExistingUser | None: ...

    def create_user_with_initial_credit(
        self,
        identity: IdentityClaims,
        initial_credit_grant: int,
        is_admin: bool,
    ) -> uuid.UUID: ...


class SqlAlchemyUserStore:
    def __init__(self, session: Session):
        self._session = session

    def find_by_google_sub(self, google_sub: str) -> ExistingUser | None:
        existing = self._session.execute(
            select(User).where(User.google_sub == google_sub)
        ).scalar_one_or_none()
        if existing is None:
            return None
        return ExistingUser(user_id=existing.user_id)

    def create_user_with_initial_credit(
        self,
        identity: IdentityClaims,
        initial_credit_grant: int,
        is_admin: bool,
    ) -> uuid.UUID:
        user_id = uuid.uuid4()
        user = User(
            user_id=user_id,
            google_sub=identity.google_sub,
            email=identity.email,
            display_name=identity.display_name,
            is_admin=is_admin,
            tos_accepted_at=datetime.now(timezone.utc),
        )
        account = UserCreditAccount(
            account_id=uuid.uuid4(),
            user_id=user_id,
            balance=initial_credit_grant,
        )
        credit_tx = CreditTransaction(
            transaction_id=uuid.uuid4(),
            user_id=user_id,
            type="grant",
            amount=initial_credit_grant,
            balance_after=initial_credit_grant,
        )
        self._session.add(user)
        self._session.add(account)
        # Flush user and account so their PKs exist in the DB before the
        # credit_transaction FK constraint is evaluated on commit.
        self._session.flush()
        self._session.add(credit_tx)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        return user_id


def provision_user(session: Session, identity: IdentityClaims) -> ProvisioningResult:
    store = SqlAlchemyUserStore(session=session)
    grant = _initial_credit_grant(session)
    return provision_user_with_store(store=store, identity=identity, initial_credit_grant=grant)


def provision_user_with_store(
    store: UserStore,
    identity: IdentityClaims,
    initial_credit_grant: int | None = None,
) -> ProvisioningResult:
    def emit_auth_event(event_name: AuthEventName, user_id: uuid.UUID) -> None:
        try:
            emit_event(event_name, user_id)
        except Exception:
            log_structured(
                logger=logger,
                level=logging.WARNING,
                message="Failed to emit auth analytics event.",
                payload={"event_name": event_name, "user_id": str(user_id)},
                exc_info=True,
            )

    existing = store.find_by_google_sub(identity.google_sub)
    if existing is not None:
        emit_auth_event("user_signed_in", existing.user_id)
        return ProvisioningResult(user_id=existing.user_id, is_new_user=False)

    grant = initial_credit_grant if initial_credit_grant is not None else _initial_credit_grant()
    try:
        user_id = store.create_user_with_initial_credit(
            identity=identity,
            initial_credit_grant=grant,
            is_admin=_is_admin_email(identity.email),
        )
    except IntegrityError:
        # Idempotency: if a concurrent request created user first, return existing row.
        existing_after_conflict = store.find_by_google_sub(identity.google_sub)
        if existing_after_conflict is None:
            raise
        emit_auth_event("user_signed_in", existing_after_conflict.user_id)
        return ProvisioningResult(
            user_id=existing_after_conflict.user_id, is_new_user=False
        )

    emit_auth_event("user_registered", user_id)
    emit_auth_event("user_signed_in", user_id)
    return ProvisioningResult(user_id=user_id, is_new_user=True)
