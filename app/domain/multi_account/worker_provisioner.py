"""Idempotent isolated-worker provisioner (Phase 1B control plane).

Allocates capacity + creates a WorkerRuntime. Does not start a real MT5
terminal by itself — that requires a Windows worker agent on a provisioned
host. Duplicate requests for the same user/account return the existing
active runtime.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.multi_account.capacity import InMemoryCapacityManager
from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_runtime import WorkerRuntime


@dataclass
class InMemoryWorkerProvisioner:
    """Control-plane provisioner with uniqueness and idempotency."""

    capacity: InMemoryCapacityManager
    _lock: Lock = field(default_factory=Lock)
    _by_id: dict[UUID, WorkerRuntime] = field(default_factory=dict)
    _active_by_user: dict[UUID, UUID] = field(default_factory=dict)
    _active_by_account: dict[UUID, UUID] = field(default_factory=dict)

    def reset(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._active_by_user.clear()
            self._active_by_account.clear()
        self.capacity.reset()

    def get(self, worker_id: UUID) -> WorkerRuntime | None:
        with self._lock:
            return self._by_id.get(worker_id)

    def require_owner(self, *, worker_id: UUID, user_id: UUID) -> WorkerRuntime:
        worker = self.get(worker_id)
        if worker is None or worker.user_id != user_id:
            raise NotFoundError(
                "Worker not found",
                details={"worker_id": str(worker_id)},
            )
        return worker

    def active_for_user(self, user_id: UUID) -> WorkerRuntime | None:
        with self._lock:
            wid = self._active_by_user.get(user_id)
            return self._by_id.get(wid) if wid else None

    def active_for_account(self, broker_account_id: UUID) -> WorkerRuntime | None:
        with self._lock:
            wid = self._active_by_account.get(broker_account_id)
            return self._by_id.get(wid) if wid else None

    def list_for_user(self, user_id: UUID) -> list[WorkerRuntime]:
        with self._lock:
            return [w for w in self._by_id.values() if w.user_id == user_id]

    def list_all(self) -> list[WorkerRuntime]:
        with self._lock:
            return list(self._by_id.values())

    def provision(
        self,
        *,
        user_id: UUID,
        broker_account_id: UUID,
        account_owner_user_id: UUID,
        worker_code: str | None = None,
        host_id: UUID | None = None,
        gateway_base_url: str = "",
        metadata: dict[str, object] | None = None,
    ) -> WorkerRuntime:
        """Allocate or return existing active runtime (idempotent)."""
        if user_id != account_owner_user_id:
            raise NotFoundError(
                "Broker account not found",
                details={"broker_account_id": str(broker_account_id)},
            )
        with self._lock:
            existing_user = self._active_by_user.get(user_id)
            if existing_user is not None:
                current = self._by_id[existing_user]
                if current.broker_account_id != broker_account_id:
                    raise ConflictError(
                        "User already has an active worker for another account",
                        details={
                            "user_id": str(user_id),
                            "existing_worker_id": str(current.worker_id),
                            "existing_broker_account_id": str(
                                current.broker_account_id
                            ),
                        },
                    )
                return current
            existing_acct = self._active_by_account.get(broker_account_id)
            if existing_acct is not None:
                raise ConflictError(
                    "Broker account already has an active worker",
                    details={"broker_account_id": str(broker_account_id)},
                )

        host = self.capacity.allocate_slot(host_id)
        code = (
            worker_code or ""
        ).strip() or f"worker-{user_id.hex[:8]}-{host.host_code}"
        runtime = WorkerRuntime.create(
            user_id=user_id,
            broker_account_id=broker_account_id,
            host_id=host.host_id,
            worker_code=code,
            gateway_base_url=gateway_base_url,
            metadata=dict(metadata or {}),
        ).with_lifecycle(WorkerLifecycleState.PROVISIONING)

        with self._lock:
            # Re-check after capacity allocation (race).
            prior_user = self._active_by_user.get(user_id)
            prior_acct = self._active_by_account.get(broker_account_id)
            if prior_user is not None or prior_acct is not None:
                self.capacity.release_slot(host.host_id)
                if prior_user is not None:
                    return self._by_id[prior_user]
                raise ConflictError(
                    "Duplicate provisioning race detected",
                    details={"user_id": str(user_id)},
                )
            self._by_id[runtime.worker_id] = runtime
            self._active_by_user[user_id] = runtime.worker_id
            self._active_by_account[broker_account_id] = runtime.worker_id
            return runtime

    def save(self, runtime: WorkerRuntime) -> WorkerRuntime:
        with self._lock:
            current = self._by_id.get(runtime.worker_id)
            if current is None:
                raise NotFoundError(
                    "Worker not found",
                    details={"worker_id": str(runtime.worker_id)},
                )
            if current.user_id != runtime.user_id:
                raise ValidationError(
                    "Cannot reassign worker to another user",
                    details={"worker_id": str(runtime.worker_id)},
                )
            self._by_id[runtime.worker_id] = runtime
            if runtime.lifecycle in {
                WorkerLifecycleState.STOPPED,
                WorkerLifecycleState.REVOKED,
            }:
                if self._active_by_user.get(runtime.user_id) == runtime.worker_id:
                    del self._active_by_user[runtime.user_id]
                if (
                    self._active_by_account.get(runtime.broker_account_id)
                    == runtime.worker_id
                ):
                    del self._active_by_account[runtime.broker_account_id]
            else:
                self._active_by_user[runtime.user_id] = runtime.worker_id
                self._active_by_account[runtime.broker_account_id] = runtime.worker_id
            return runtime

    def stop(self, *, worker_id: UUID, user_id: UUID) -> WorkerRuntime:
        worker = self.require_owner(worker_id=worker_id, user_id=user_id)
        stopping = worker.with_lifecycle(WorkerLifecycleState.STOPPING)
        stopped = stopping.with_lifecycle(WorkerLifecycleState.STOPPED)
        saved = self.save(stopped)
        with contextlib.suppress(NotFoundError):
            self.capacity.release_slot(saved.host_id)
        return saved

    def revoke(self, *, worker_id: UUID, user_id: UUID) -> WorkerRuntime:
        worker = self.require_owner(worker_id=worker_id, user_id=user_id)
        if worker.lifecycle is not WorkerLifecycleState.REVOKED:
            try:
                revoked = worker.with_lifecycle(WorkerLifecycleState.REVOKED)
            except ValidationError:
                # Force via STOPPING/STOPPED path when needed.
                mid = worker
                if mid.lifecycle not in {
                    WorkerLifecycleState.STOPPING,
                    WorkerLifecycleState.STOPPED,
                }:
                    if mid.lifecycle not in {
                        WorkerLifecycleState.ERROR,
                        WorkerLifecycleState.PENDING,
                    }:
                        mid = mid.with_lifecycle(WorkerLifecycleState.STOPPING)
                    mid = mid.with_lifecycle(WorkerLifecycleState.STOPPED)
                revoked = mid.with_lifecycle(WorkerLifecycleState.REVOKED)
            saved = self.save(revoked)
            with contextlib.suppress(NotFoundError):
                self.capacity.release_slot(saved.host_id)
            return saved
        return worker
