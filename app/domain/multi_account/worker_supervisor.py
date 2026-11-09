"""Worker supervisor — heartbeat, stale detection, independent restart.

A failure or restart for one worker must not mutate other workers.
Controlled exponential backoff is recorded on the runtime attempt_count;
actual process restart is performed by the Windows agent when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.exceptions.base import ValidationError
from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_provisioner import InMemoryWorkerProvisioner
from app.domain.multi_account.worker_runtime import WorkerRuntime


def restart_backoff_seconds(
    attempt_count: int, *, base: float = 2.0, cap: float = 60.0
) -> float:
    """Bounded exponential backoff for reconnect/restart attempts."""
    n = max(0, int(attempt_count))
    delay = min(cap, base * (2**n))
    return float(delay)


@dataclass
class WorkerSupervisor:
    provisioner: InMemoryWorkerProvisioner
    stale_after: timedelta = timedelta(seconds=45)

    def record_heartbeat(
        self, *, worker_id: UUID, user_id: UUID, now: datetime | None = None
    ) -> WorkerRuntime:
        worker = self.provisioner.require_owner(worker_id=worker_id, user_id=user_id)
        updated = worker.heartbeat(now=now)
        return self.provisioner.save(updated)

    def detect_stale(self, *, now: datetime | None = None) -> list[WorkerRuntime]:
        stamp = now or datetime.now(UTC)
        stale: list[WorkerRuntime] = []
        for worker in self.provisioner.list_all():
            if worker.lifecycle in {
                WorkerLifecycleState.STOPPED,
                WorkerLifecycleState.REVOKED,
                WorkerLifecycleState.PENDING,
            }:
                continue
            if worker.is_heartbeat_stale(now=stamp, max_age=self.stale_after):
                marked = worker.with_lifecycle(
                    (
                        WorkerLifecycleState.DISCONNECTED
                        if worker.lifecycle is WorkerLifecycleState.READY
                        else WorkerLifecycleState.ERROR
                    ),
                    error="heartbeat_stale",
                )
                stale.append(self.provisioner.save(marked))
        return stale

    def request_reconnect(
        self, *, worker_id: UUID, user_id: UUID
    ) -> tuple[WorkerRuntime, float]:
        """Move a failed/disconnected worker toward RECONNECTING independently."""
        worker = self.provisioner.require_owner(worker_id=worker_id, user_id=user_id)
        if worker.lifecycle is WorkerLifecycleState.READY:
            raise ValidationError(
                "Worker is READY; disconnect first before reconnect",
                details={"worker_id": str(worker_id)},
            )
        if worker.lifecycle is WorkerLifecycleState.REVOKED:
            raise ValidationError(
                "Cannot reconnect a revoked worker",
                details={"worker_id": str(worker_id)},
            )
        current = worker
        if current.lifecycle not in {
            WorkerLifecycleState.DISCONNECTED,
            WorkerLifecycleState.ERROR,
        }:
            # Allow from ERROR/DISCONNECTED primarily; force via ERROR if needed.
            if current.lifecycle in {
                WorkerLifecycleState.AUTHENTICATING,
                WorkerLifecycleState.VERIFYING,
                WorkerLifecycleState.STARTING,
                WorkerLifecycleState.PROVISIONING,
                WorkerLifecycleState.RECONNECTING,
            }:
                current = current.with_lifecycle(
                    WorkerLifecycleState.ERROR, error="reconnect_requested"
                )
            else:
                current = current.with_lifecycle(WorkerLifecycleState.DISCONNECTED)
        reconnecting = current.with_lifecycle(WorkerLifecycleState.RECONNECTING)
        saved = self.provisioner.save(reconnecting)
        delay = restart_backoff_seconds(saved.attempt_count)
        return saved, delay

    def advance_start_auth_verify(
        self,
        *,
        worker_id: UUID,
        user_id: UUID,
        login: str,
        server: str,
        trade_allowed: bool,
        runtime_session_id: str,
    ) -> WorkerRuntime:
        """Drive STARTING→AUTH→VERIFY→READY for a single worker after agent reports."""
        worker = self.provisioner.require_owner(worker_id=worker_id, user_id=user_id)
        current = worker
        if current.lifecycle in {
            WorkerLifecycleState.PROVISIONING,
            WorkerLifecycleState.RECONNECTING,
            WorkerLifecycleState.PENDING,
        }:
            current = current.with_lifecycle(WorkerLifecycleState.STARTING)
        if current.lifecycle is WorkerLifecycleState.STARTING:
            current = current.with_lifecycle(WorkerLifecycleState.AUTHENTICATING)
        if current.lifecycle is WorkerLifecycleState.AUTHENTICATING:
            current = current.with_lifecycle(WorkerLifecycleState.VERIFYING)
        verified = current.mark_verified(
            login=login,
            server=server,
            trade_allowed=trade_allowed,
            runtime_session_id=runtime_session_id,
        )
        return self.provisioner.save(verified)

    def fail_worker(
        self, *, worker_id: UUID, user_id: UUID, reason: str
    ) -> WorkerRuntime:
        worker = self.provisioner.require_owner(worker_id=worker_id, user_id=user_id)
        if worker.lifecycle is WorkerLifecycleState.REVOKED:
            return worker
        failed = worker.with_lifecycle(
            WorkerLifecycleState.ERROR, error=(reason or "worker_error")[:500]
        )
        return self.provisioner.save(failed)
