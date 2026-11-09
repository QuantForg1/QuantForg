"""MT5 account ownership claims (Phase 1a registry).

Product rule: one QuantForg user may own at most ONE non-revoked MT5 account.
Global uniqueness on (broker_id, normalized_server, normalized_login) prevents
two users claiming the same trading login.

Many users may each register one account. This module does **not** provision
isolated MT5 terminals or enable multi-user LIVE execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError


def normalize_mt5_login(login: str) -> str:
    return (login or "").strip().lower()


def normalize_broker_server(server: str) -> str:
    return (server or "").strip().lower()


def ownership_claim_key(
    *,
    broker_id: UUID,
    server: str,
    login: str,
) -> tuple[UUID, str, str]:
    normalized_login = normalize_mt5_login(login)
    if not normalized_login:
        raise ValidationError(
            "MT5 login is required for ownership claim",
            details={"field": "external_account_id"},
        )
    return (
        broker_id,
        normalize_broker_server(server),
        normalized_login,
    )


@dataclass(frozen=True, slots=True)
class AccountOwnershipRecord:
    """Registry row for one user-linked broker account claim."""

    account_id: UUID
    user_id: UUID
    broker_id: UUID
    login: str
    server: str
    status: str = "pending"  # pending | active | inactive | revoked
    ownership_verified: bool = False
    ownership_verified_at: datetime | None = None
    label: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def claim_key(self) -> tuple[UUID, str, str]:
        return ownership_claim_key(
            broker_id=self.broker_id,
            server=self.server,
            login=self.login,
        )

    @property
    def is_claim_active(self) -> bool:
        return self.status != "revoked"


class BrokerAuthPort(Protocol):
    """Validate credentials without retaining a LIVE shared session.

    Phase 1a tests use mocks. Production wiring must use an isolated worker
    when simultaneous multi-account execution is introduced (not yet).
    """

    async def validate_credentials(
        self,
        *,
        login: str,
        password: str,
        server: str,
    ) -> bool: ...


@dataclass
class InMemoryOwnershipClaimRegistry:
    """Thread-safe claim map mirroring the DB unique index semantics."""

    _lock: Lock = field(default_factory=Lock)
    _by_id: dict[UUID, AccountOwnershipRecord] = field(default_factory=dict)
    _active_claims: dict[tuple[UUID, str, str], UUID] = field(default_factory=dict)
    _active_by_user: dict[UUID, UUID] = field(default_factory=dict)

    def reset(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._active_claims.clear()
            self._active_by_user.clear()

    def get(self, account_id: UUID) -> AccountOwnershipRecord | None:
        with self._lock:
            return self._by_id.get(account_id)

    def list_for_user(self, user_id: UUID) -> list[AccountOwnershipRecord]:
        with self._lock:
            return [r for r in self._by_id.values() if r.user_id == user_id]

    def active_for_user(self, user_id: UUID) -> AccountOwnershipRecord | None:
        with self._lock:
            account_id = self._active_by_user.get(user_id)
            return self._by_id.get(account_id) if account_id else None

    def find_active_claim(
        self,
        *,
        broker_id: UUID,
        server: str,
        login: str,
    ) -> AccountOwnershipRecord | None:
        key = ownership_claim_key(broker_id=broker_id, server=server, login=login)
        with self._lock:
            account_id = self._active_claims.get(key)
            if account_id is None:
                return None
            return self._by_id.get(account_id)

    def register_claim(
        self,
        *,
        user_id: UUID,
        broker_id: UUID,
        login: str,
        server: str,
        label: str = "",
        account_id: UUID | None = None,
    ) -> AccountOwnershipRecord:
        """Atomically reserve ownership (pending, unverified).

        Enforces one non-revoked account per user and global login uniqueness.
        """
        key = ownership_claim_key(broker_id=broker_id, server=server, login=login)
        record = AccountOwnershipRecord(
            account_id=account_id or uuid4(),
            user_id=user_id,
            broker_id=broker_id,
            login=normalize_mt5_login(login),
            server=normalize_broker_server(server),
            status="pending",
            ownership_verified=False,
            label=(label or "").strip(),
        )
        with self._lock:
            if user_id in self._active_by_user:
                raise ConflictError(
                    "User already has an active MT5 trading account",
                    details={
                        "user_id": str(user_id),
                        "existing_account_id": str(self._active_by_user[user_id]),
                    },
                )
            existing_id = self._active_claims.get(key)
            if existing_id is not None:
                existing = self._by_id[existing_id]
                raise ConflictError(
                    "Broker account login already claimed by another user",
                    details={
                        "broker_id": str(broker_id),
                        "server": key[1],
                        "login": key[2],
                        "owner_user_id": str(existing.user_id),
                        "account_id": str(existing.account_id),
                    },
                )
            self._by_id[record.account_id] = record
            self._active_claims[key] = record.account_id
            self._active_by_user[user_id] = record.account_id
            return record

    def require_owner(
        self, *, account_id: UUID, user_id: UUID
    ) -> AccountOwnershipRecord:
        with self._lock:
            record = self._by_id.get(account_id)
            if record is None or record.user_id != user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(account_id)},
                )
            return record

    async def verify_ownership(
        self,
        *,
        account_id: UUID,
        user_id: UUID,
        password: str,
        auth: BrokerAuthPort,
    ) -> AccountOwnershipRecord:
        """Mark verified only after successful broker authentication."""
        record = self.require_owner(account_id=account_id, user_id=user_id)
        if record.status == "revoked":
            raise ValidationError(
                "Cannot verify a revoked broker account",
                details={"account_id": str(account_id)},
            )
        if not (password or "").strip():
            raise ValidationError(
                "Password required for ownership verification",
                details={"field": "password"},
            )
        ok = await auth.validate_credentials(
            login=record.login,
            password=password,
            server=record.server,
        )
        if not ok:
            raise ValidationError(
                "Broker authentication failed — ownership not verified",
                details={"account_id": str(account_id)},
            )
        verified = AccountOwnershipRecord(
            account_id=record.account_id,
            user_id=record.user_id,
            broker_id=record.broker_id,
            login=record.login,
            server=record.server,
            status="active",
            ownership_verified=True,
            ownership_verified_at=datetime.now(UTC),
            label=record.label,
            created_at=record.created_at,
        )
        with self._lock:
            self._by_id[account_id] = verified
            return verified

    def revoke(self, *, account_id: UUID, user_id: UUID) -> AccountOwnershipRecord:
        """Revoke ownership and release the global claim for reconnect."""
        record = self.require_owner(account_id=account_id, user_id=user_id)
        if record.status == "revoked":
            return record
        revoked = AccountOwnershipRecord(
            account_id=record.account_id,
            user_id=record.user_id,
            broker_id=record.broker_id,
            login=record.login,
            server=record.server,
            status="revoked",
            ownership_verified=False,
            ownership_verified_at=None,
            label=record.label,
            created_at=record.created_at,
        )
        with self._lock:
            self._by_id[account_id] = revoked
            self._active_claims.pop(record.claim_key, None)
            if self._active_by_user.get(user_id) == account_id:
                del self._active_by_user[user_id]
            return revoked

    def reconnect_claim(
        self,
        *,
        user_id: UUID,
        broker_id: UUID,
        login: str,
        server: str,
        label: str = "",
    ) -> AccountOwnershipRecord:
        """Re-register after revoke (or first claim). Same uniqueness rules."""
        return self.register_claim(
            user_id=user_id,
            broker_id=broker_id,
            login=login,
            server=server,
            label=label,
        )
