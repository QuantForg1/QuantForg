"""MT5 multi-user worker control plane (Phase 1B).

Orchestrates provisioner + supervisor + agent port. Does not enable LIVE
signal fan-out. Does not replace the Weltrade singleton gateway.

Credential passwords are accepted only as transient arguments for the agent
authenticate call and are never stored on worker metadata or logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.exceptions.base import ValidationError
from app.domain.multi_account.capacity import InMemoryCapacityManager
from app.domain.multi_account.feature_gates import multi_account_live_submit_allowed
from app.domain.multi_account.worker_agent_protocol import (
    AgentAuthRequest,
    Mt5WorkerAgentPort,
)
from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_provisioner import InMemoryWorkerProvisioner
from app.domain.multi_account.worker_runtime import WorkerRuntime
from app.domain.multi_account.worker_supervisor import WorkerSupervisor

logger = logging.getLogger(__name__)


def _redact(_: str) -> str:
    return "***"


@dataclass
class Mt5WorkerControlPlane:
    """In-process control plane for tests and future host wiring."""

    capacity: InMemoryCapacityManager = field(default_factory=InMemoryCapacityManager)
    provisioner: InMemoryWorkerProvisioner | None = None
    supervisor: WorkerSupervisor | None = None
    agent: Mt5WorkerAgentPort | None = None
    service_token: str = "dev-worker-service-token"  # noqa: S105

    def __post_init__(self) -> None:
        if self.provisioner is None:
            self.provisioner = InMemoryWorkerProvisioner(capacity=self.capacity)
        assert self.provisioner is not None
        if self.supervisor is None:
            self.supervisor = WorkerSupervisor(provisioner=self.provisioner)

    def reset(self) -> None:
        assert self.provisioner is not None
        self.provisioner.reset()

    def register_host(
        self, *, host_code: str, max_terminals: int, region: str = ""
    ) -> Any:
        return self.capacity.register_host(
            host_code=host_code, max_terminals=max_terminals, region=region
        )

    def provision_worker(
        self,
        *,
        user_id: UUID,
        broker_account_id: UUID,
        host_id: UUID | None = None,
    ) -> WorkerRuntime:
        assert self.provisioner is not None
        return self.provisioner.provision(
            user_id=user_id,
            broker_account_id=broker_account_id,
            account_owner_user_id=user_id,
            host_id=host_id,
        )

    async def connect_and_verify(
        self,
        *,
        worker_id: UUID,
        user_id: UUID,
        login: str,
        server: str,
        password: str,
    ) -> WorkerRuntime:
        """Start agent terminal, authenticate, verify — single worker only.

        Never logs ``password``. Investor/read-only credentials fail closed.
        """
        if self.agent is None:
            raise ValidationError(
                "No MT5 worker agent bound to control plane",
                details={"worker_id": str(worker_id)},
            )
        assert self.supervisor is not None
        assert self.provisioner is not None
        worker = self.provisioner.require_owner(worker_id=worker_id, user_id=user_id)
        _ = _redact(password)

        started = await self.agent.start_terminal(worker_id=worker_id)
        if not started:
            return self.supervisor.fail_worker(
                worker_id=worker_id, user_id=user_id, reason="terminal_start_failed"
            )

        current = worker
        if current.lifecycle is WorkerLifecycleState.PROVISIONING:
            current = current.with_lifecycle(WorkerLifecycleState.STARTING)
            current = self.provisioner.save(current)

        auth = await self.agent.authenticate(
            AgentAuthRequest(
                worker_id=worker_id,
                user_id=user_id,
                broker_account_id=worker.broker_account_id,
                login=login,
                server=server,
                password=password,
                service_token=self.service_token,
            )
        )
        # Intentionally do not include password in any log fields.
        logger.info(
            "mt5_worker_auth_result worker_id=%s ok=%s trade_allowed=%s error=%s",
            worker_id,
            auth.ok,
            auth.trade_allowed,
            auth.error or "",
        )
        if not auth.ok or not auth.trade_allowed:
            return self.supervisor.fail_worker(
                worker_id=worker_id,
                user_id=user_id,
                reason=auth.error or "authentication_failed",
            )

        self.supervisor.advance_start_auth_verify(
            worker_id=worker_id,
            user_id=user_id,
            login=auth.verified_login or login,
            server=auth.verified_server or server,
            trade_allowed=auth.trade_allowed,
            runtime_session_id=auth.runtime_session_id,
        )
        return self.supervisor.record_heartbeat(worker_id=worker_id, user_id=user_id)

    async def disconnect(self, *, worker_id: UUID, user_id: UUID) -> WorkerRuntime:
        assert self.provisioner is not None
        if self.agent is not None:
            await self.agent.disconnect(worker_id=worker_id)
        return self.provisioner.stop(worker_id=worker_id, user_id=user_id)

    def heartbeat(
        self, *, worker_id: UUID, user_id: UUID, now: datetime | None = None
    ) -> WorkerRuntime:
        assert self.supervisor is not None
        return self.supervisor.record_heartbeat(
            worker_id=worker_id, user_id=user_id, now=now
        )

    def scan_stale(self, *, now: datetime | None = None) -> list[WorkerRuntime]:
        assert self.supervisor is not None
        return self.supervisor.detect_stale(now=now)

    def status_for_user(self, user_id: UUID) -> dict[str, Any]:
        assert self.provisioner is not None
        active = self.provisioner.active_for_user(user_id)
        return {
            "user_id": str(user_id),
            "worker": active.public_status() if active else None,
            "live_submit_enabled": multi_account_live_submit_allowed(),
            "capacity": self.capacity.summary(),
            "note": (
                "Control-plane status only. READY requires agent auth+verify; "
                "mocked agents are not real MT5 terminals."
            ),
        }
