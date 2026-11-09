"""Execution worker *assignment* registry (Phase 1a).

Product rule: one user → one MT5 account → one active worker assignment.

Each future worker will own an isolated MT5 terminal/session for that user.
This module stores assignment metadata only — placeholder rows are NOT
running terminals and do NOT prove concurrent LIVE execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError

FORBIDDEN_WORKER_METADATA_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "api_key",
        "api_secret",
        "token",
        "secret",
        "credential",
        "credentials",
        "encrypted_payload",
        "authorization",
        "auth",
        "mt5_password",
        "investor_password",
    }
)

_ACTIVE_STATUSES = frozenset({"registered", "healthy", "degraded", "offline"})


def assert_tenant_safe_worker_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Reject credential-like keys. Returns a shallow sanitized copy."""
    raw = dict(metadata or {})
    blocked = [
        key
        for key in raw
        if str(key).strip().lower() in FORBIDDEN_WORKER_METADATA_KEYS
        or "password" in str(key).strip().lower()
        or "secret" in str(key).strip().lower()
        or "token" in str(key).strip().lower()
    ]
    if blocked:
        raise ValidationError(
            "Worker metadata must not contain credentials or secrets",
            details={"blocked_keys": blocked},
        )
    return {str(k): v for k, v in raw.items()}


@dataclass(frozen=True, slots=True)
class ExecutionWorkerAssignment:
    """One registry row: planned binding of a worker to one broker account."""

    worker_id: UUID
    worker_code: str
    user_id: UUID
    broker_account_id: UUID
    status: str = "registered"
    platform_code: str = "mt5"
    gateway_base_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_active_assignment(self) -> bool:
        return self.status in _ACTIVE_STATUSES


@dataclass
class InMemoryExecutionWorkerRegistry:
    """Enforces one active worker assignment per broker account."""

    _lock: Lock = field(default_factory=Lock)
    _by_id: dict[UUID, ExecutionWorkerAssignment] = field(default_factory=dict)
    _active_by_account: dict[UUID, UUID] = field(default_factory=dict)
    _active_by_user: dict[UUID, UUID] = field(default_factory=dict)
    _codes: dict[str, UUID] = field(default_factory=dict)

    def reset(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._active_by_account.clear()
            self._active_by_user.clear()
            self._codes.clear()

    def get(self, worker_id: UUID) -> ExecutionWorkerAssignment | None:
        with self._lock:
            return self._by_id.get(worker_id)

    def active_for_account(
        self, broker_account_id: UUID
    ) -> ExecutionWorkerAssignment | None:
        with self._lock:
            wid = self._active_by_account.get(broker_account_id)
            return self._by_id.get(wid) if wid else None

    def active_for_user(self, user_id: UUID) -> ExecutionWorkerAssignment | None:
        with self._lock:
            wid = self._active_by_user.get(user_id)
            return self._by_id.get(wid) if wid else None

    def list_for_user(self, user_id: UUID) -> list[ExecutionWorkerAssignment]:
        with self._lock:
            return [w for w in self._by_id.values() if w.user_id == user_id]

    def assign(
        self,
        *,
        user_id: UUID,
        broker_account_id: UUID,
        worker_code: str,
        account_owner_user_id: UUID,
        gateway_base_url: str = "",
        metadata: Mapping[str, Any] | None = None,
        platform_code: str = "mt5",
    ) -> ExecutionWorkerAssignment:
        """Register an active worker assignment (metadata only; no LIVE)."""
        if user_id != account_owner_user_id:
            raise NotFoundError(
                "Broker account not found",
                details={"broker_account_id": str(broker_account_id)},
            )
        code = (worker_code or "").strip()
        if not code:
            raise ValidationError(
                "worker_code is required",
                details={"field": "worker_code"},
            )
        safe_meta = assert_tenant_safe_worker_metadata(metadata)
        assignment = ExecutionWorkerAssignment(
            worker_id=uuid4(),
            worker_code=code,
            user_id=user_id,
            broker_account_id=broker_account_id,
            status="registered",
            platform_code=(platform_code or "mt5").strip().lower() or "mt5",
            gateway_base_url=(gateway_base_url or "").strip(),
            metadata=safe_meta,
        )
        with self._lock:
            if code.lower() in self._codes:
                raise ConflictError(
                    "worker_code already registered",
                    details={"worker_code": code},
                )
            if user_id in self._active_by_user:
                raise ConflictError(
                    "User already has an active worker assignment",
                    details={"user_id": str(user_id)},
                )
            if broker_account_id in self._active_by_account:
                raise ConflictError(
                    "Broker account already has an active worker assignment",
                    details={"broker_account_id": str(broker_account_id)},
                )
            self._by_id[assignment.worker_id] = assignment
            self._active_by_account[broker_account_id] = assignment.worker_id
            self._active_by_user[user_id] = assignment.worker_id
            self._codes[code.lower()] = assignment.worker_id
            return assignment

    def disable(self, *, worker_id: UUID, user_id: UUID) -> ExecutionWorkerAssignment:
        """Disable assignment and free the user/account slot for reconnect."""
        with self._lock:
            current = self._by_id.get(worker_id)
            if current is None or current.user_id != user_id:
                raise NotFoundError(
                    "Worker assignment not found",
                    details={"worker_id": str(worker_id)},
                )
            disabled = ExecutionWorkerAssignment(
                worker_id=current.worker_id,
                worker_code=current.worker_code,
                user_id=current.user_id,
                broker_account_id=current.broker_account_id,
                status="disabled",
                platform_code=current.platform_code,
                gateway_base_url=current.gateway_base_url,
                metadata=dict(current.metadata),
                created_at=current.created_at,
                updated_at=datetime.now(UTC),
            )
            self._by_id[worker_id] = disabled
            if self._active_by_account.get(current.broker_account_id) == worker_id:
                del self._active_by_account[current.broker_account_id]
            if self._active_by_user.get(current.user_id) == worker_id:
                del self._active_by_user[current.user_id]
            return disabled
