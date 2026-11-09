"""Worker runtime records — control-plane view of isolated MT5 sessions.

Passwords and credential payloads are forbidden in metadata and never stored
on this record. Credentials are fetched by the Windows agent from the
backend over an authenticated channel only when authenticating.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.domain.multi_account.execution_worker_registry import (
    assert_tenant_safe_worker_metadata,
)
from app.domain.multi_account.worker_lifecycle import (
    WorkerLifecycleState,
    assert_not_connected_until_ready,
    is_session_ready,
    transition,
)


@dataclass(frozen=True, slots=True)
class WorkerRuntime:
    """One isolated worker runtime assignment for one user account."""

    worker_id: UUID
    worker_code: str
    user_id: UUID
    broker_account_id: UUID
    host_id: UUID
    lifecycle: WorkerLifecycleState = WorkerLifecycleState.PENDING
    runtime_session_id: str = ""
    gateway_base_url: str = ""
    last_heartbeat_at: datetime | None = None
    last_health_check_at: datetime | None = None
    last_error: str = ""
    attempt_count: int = 0
    trade_allowed: bool | None = None
    account_login_verified: str = ""
    server_verified: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        broker_account_id: UUID,
        host_id: UUID,
        worker_code: str,
        gateway_base_url: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkerRuntime:
        return cls(
            worker_id=uuid4(),
            worker_code=worker_code.strip(),
            user_id=user_id,
            broker_account_id=broker_account_id,
            host_id=host_id,
            lifecycle=WorkerLifecycleState.PENDING,
            gateway_base_url=(gateway_base_url or "").strip(),
            metadata=assert_tenant_safe_worker_metadata(metadata),
        )

    @property
    def is_ready(self) -> bool:
        return is_session_ready(self.lifecycle)

    def with_lifecycle(
        self, target: WorkerLifecycleState, *, error: str | None = None
    ) -> WorkerRuntime:
        new_state = transition(self.lifecycle, target)
        return replace(
            self,
            lifecycle=new_state,
            last_error=(error if error is not None else self.last_error),
            updated_at=datetime.now(UTC),
            attempt_count=(
                self.attempt_count + 1
                if target
                in {
                    WorkerLifecycleState.AUTHENTICATING,
                    WorkerLifecycleState.RECONNECTING,
                    WorkerLifecycleState.STARTING,
                }
                else self.attempt_count
            ),
        )

    def heartbeat(self, *, now: datetime | None = None) -> WorkerRuntime:
        stamp = now or datetime.now(UTC)
        return replace(
            self,
            last_heartbeat_at=stamp,
            last_health_check_at=stamp,
            updated_at=stamp,
        )

    def mark_verified(
        self,
        *,
        login: str,
        server: str,
        trade_allowed: bool,
        runtime_session_id: str,
    ) -> WorkerRuntime:
        """Promote VERIFYING → READY only when trade permission is present."""
        if self.lifecycle is not WorkerLifecycleState.VERIFYING:
            raised = self.with_lifecycle(WorkerLifecycleState.VERIFYING)
        else:
            raised = self
        if not trade_allowed:
            return raised.with_lifecycle(
                WorkerLifecycleState.ERROR,
                error="investor_or_readonly_credentials_rejected",
            )
        ready = raised.with_lifecycle(WorkerLifecycleState.READY)
        assert_not_connected_until_ready(ready.lifecycle, "READY")
        return replace(
            ready,
            account_login_verified=(login or "").strip(),
            server_verified=(server or "").strip(),
            trade_allowed=True,
            runtime_session_id=(runtime_session_id or "").strip(),
            last_error="",
            updated_at=datetime.now(UTC),
        )

    def is_heartbeat_stale(
        self, *, now: datetime | None = None, max_age: timedelta = timedelta(seconds=45)
    ) -> bool:
        if self.last_heartbeat_at is None:
            return self.lifecycle not in {
                WorkerLifecycleState.PENDING,
                WorkerLifecycleState.PROVISIONING,
                WorkerLifecycleState.STOPPED,
                WorkerLifecycleState.REVOKED,
            }
        stamp = now or datetime.now(UTC)
        return stamp - self.last_heartbeat_at > max_age

    def public_status(self) -> dict[str, Any]:
        """Safe status for APIs — never includes secrets."""
        connected = self.is_ready
        return {
            "worker_id": str(self.worker_id),
            "user_id": str(self.user_id),
            "broker_account_id": str(self.broker_account_id),
            "host_id": str(self.host_id),
            "lifecycle": self.lifecycle.value,
            "connected": connected,
            "ready": connected,
            "runtime_session_id": self.runtime_session_id,
            "last_heartbeat_at": (
                self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None
            ),
            "last_error": self.last_error,
            "trade_allowed": self.trade_allowed,
            "account_login_verified": self.account_login_verified,
            "server_verified": self.server_verified,
            "attempt_count": self.attempt_count,
        }
