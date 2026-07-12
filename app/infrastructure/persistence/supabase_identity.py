"""Supabase PostgREST persistence for identity profiles and audit logs.

Uses existing ``public.users`` / ``public.audit_logs`` migrations. Credentials
remain in Supabase Auth (``auth.users``); this adapter only stores application
profile rows linked by ``auth_user_id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
from app.domain.entities.user import User
from app.domain.enums.user import UserRole, UserStatus
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import PersonName
from app.infrastructure.supabase.client import SupabaseClient
from core.logging import get_logger

logger = get_logger(__name__)


def _parse_dt(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _user_from_row(row: dict[str, Any]) -> User:
    auth_raw = row.get("auth_user_id")
    created = _parse_dt(row.get("created_at")) or datetime.now(UTC)
    updated = _parse_dt(row.get("updated_at")) or created
    return User(
        id=UUID(str(row["id"])),
        email=EmailAddress(value=str(row["email"])),
        display_name=PersonName(value=str(row["display_name"])),
        role=UserRole(str(row["role"])),
        status=UserStatus(str(row["status"])),
        password_hash=str(row.get("password_hash") or ""),
        auth_user_id=UUID(str(auth_raw)) if auth_raw else None,
        last_login_at=_parse_dt(row.get("last_login_at")),
        deactivated_at=_parse_dt(row.get("deactivated_at")),
        created_at=created,
        updated_at=updated,
    )


def _user_to_row(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": str(user.email),
        "display_name": str(user.display_name),
        "role": user.role.value,
        "status": user.status.value,
        "password_hash": user.password_hash,
        "auth_user_id": str(user.auth_user_id) if user.auth_user_id else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "deactivated_at": (
            user.deactivated_at.isoformat() if user.deactivated_at else None
        ),
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _audit_to_row(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "action": entry.action.value,
        "outcome": entry.outcome.value,
        "resource_type": entry.resource_type,
        "resource_id": str(entry.resource_id) if entry.resource_id else None,
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
        "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
        "ip_address": entry.ip_address,
        "user_agent": entry.user_agent,
        "message": entry.message,
        "metadata": entry.metadata,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


class SupabaseUserRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = (
            self._client.table("users")
            .select("*")
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return _user_from_row(rows[0]) if rows else None

    async def get_by_email(self, email: EmailAddress) -> User | None:
        result = (
            self._client.table("users")
            .select("*")
            .ilike("email", email.value)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return _user_from_row(rows[0]) if rows else None

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> User | None:
        result = (
            self._client.table("users")
            .select("*")
            .eq("auth_user_id", str(auth_user_id))
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return _user_from_row(rows[0]) if rows else None

    async def add(self, user: User) -> User:
        self._client.table("users").insert(_user_to_row(user)).execute()
        return user

    async def update(self, user: User) -> User:
        self._client.table("users").upsert(_user_to_row(user)).execute()
        return user


class SupabaseAuditLogRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def add(self, entry: AuditLog) -> AuditLog:
        self._client.table("audit_logs").insert(_audit_to_row(entry)).execute()
        return entry

    async def list_recent(self, *, limit: int = 200) -> list[AuditLog]:
        """List recent audit rows (service-role). Mapping is best-effort."""
        _ = limit
        # Identity UoW uses PostgREST; full hydrate is out of scope for ops phase.
        return []


class _UnsupportedRepository:
    """Stub for non-identity aggregates on the identity UoW."""

    def __getattr__(self, name: str) -> Any:
        msg = f"Repository operation '{name}' is not available on identity UoW"
        raise RuntimeError(msg)


@dataclass
class SupabaseIdentityUnitOfWork:
    """UoW exposing users + audit_logs via PostgREST (service role preferred)."""

    _supabase: SupabaseClient
    users: SupabaseUserRepository = field(init=False)
    audit_logs: SupabaseAuditLogRepository = field(init=False)
    licenses: Any = field(default_factory=_UnsupportedRepository, init=False)
    brokers: Any = field(default_factory=_UnsupportedRepository, init=False)
    trading_accounts: Any = field(default_factory=_UnsupportedRepository, init=False)
    trading_sessions: Any = field(default_factory=_UnsupportedRepository, init=False)
    symbols: Any = field(default_factory=_UnsupportedRepository, init=False)
    signals: Any = field(default_factory=_UnsupportedRepository, init=False)
    risk_profiles: Any = field(default_factory=_UnsupportedRepository, init=False)

    def __post_init__(self) -> None:
        client = self._supabase.admin_client
        self.users = SupabaseUserRepository(client)
        self.audit_logs = SupabaseAuditLogRepository(client)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        # PostgREST operations are applied immediately.
        return None

    async def rollback(self) -> None:
        logger.warning("supabase_identity_uow_rollback_noop")


@dataclass(frozen=True, slots=True)
class SupabaseIdentityUnitOfWorkFactory:
    supabase: SupabaseClient

    def __call__(self) -> SupabaseIdentityUnitOfWork:
        return SupabaseIdentityUnitOfWork(_supabase=self.supabase)
