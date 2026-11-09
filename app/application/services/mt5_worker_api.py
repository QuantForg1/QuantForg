"""HTTP-facing MT5 worker control-plane facade (Phase 1C).

Process-durable singleton used by Railway routes. Does not enable LIVE
multi-account submit. Passwords are never stored or returned.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid5

from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.multi_account.feature_gates import multi_account_live_submit_allowed
from app.domain.multi_account.worker_lifecycle import WorkerLifecycleState
from app.domain.multi_account.worker_runtime import WorkerRuntime

logger = logging.getLogger(__name__)

# Stable lab namespace for demo slot synthetic owners (not SaaS users).
_LAB_NS = UUID("a7c4e2f1-9b30-4d5e-8f12-6c1d0a9b8e77")


def lab_ids_for_slot(*, host_code: str, slot_id: str) -> tuple[UUID, UUID]:
    """Deterministic lab user/account UUIDs for a host slot (integration only)."""
    key = f"{host_code.strip().lower()}::{slot_id.strip().lower()}"
    return (
        uuid5(_LAB_NS, f"user:{key}"),
        uuid5(_LAB_NS, f"account:{key}"),
    )


def _slot_key(host_code: str, slot_id: str) -> str:
    return f"{host_code.strip().lower()}::{slot_id.strip().lower()}"


@dataclass
class Mt5WorkerApiFacade:
    """Durable (process-lifetime) worker registration / heartbeat / revoke API."""

    plane: Mt5WorkerControlPlane
    stale_after: timedelta = field(default_factory=lambda: timedelta(seconds=45))
    _lock: Lock = field(default_factory=Lock)
    _slot_to_worker: dict[str, UUID] = field(default_factory=dict)
    _worker_to_slot: dict[UUID, str] = field(default_factory=dict)
    _revoked_workers: set[UUID] = field(default_factory=set)

    def __post_init__(self) -> None:
        assert self.plane.supervisor is not None
        self.plane.supervisor.stale_after = self.stale_after

    def _public(self, worker: WorkerRuntime) -> dict[str, Any]:
        status = worker.public_status()
        slot = self._worker_to_slot.get(worker.worker_id, "")
        host_code = ""
        slot_id = ""
        if "::" in slot:
            host_code, slot_id = slot.split("::", 1)
        status.update(
            {
                "host_code": host_code,
                "slot_id": slot_id,
                "revoked": worker.worker_id in self._revoked_workers
                or worker.lifecycle is WorkerLifecycleState.REVOKED,
                "live_submit_enabled": multi_account_live_submit_allowed(),
                "password_included": False,
            }
        )
        return status

    def ensure_host(
        self,
        *,
        host_code: str,
        max_terminals: int = 4,
        region: str = "",
    ) -> dict[str, Any]:
        host = self.plane.capacity.ensure_host(
            host_code=host_code,
            max_terminals=max_terminals,
            region=region,
            notes="phase1c-windows-worker",
        )
        return {
            "host_id": str(host.host_id),
            "host_code": host.host_code,
            "max_terminals": host.max_terminals,
            "allocated_terminals": host.allocated_terminals,
            "free_slots": host.free_slots,
        }

    def register(
        self,
        *,
        host_code: str,
        slot_id: str,
        platform: str = "windows-local",
        max_terminals: int = 4,
        user_id: UUID | None = None,
        broker_account_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Idempotent worker registration for one host slot."""
        slot = (slot_id or "").strip().lower()
        if not slot:
            raise ValidationError("slot_id is required", details={"field": "slot_id"})
        host = self.plane.capacity.ensure_host(
            host_code=host_code,
            max_terminals=max_terminals,
            notes="phase1c-windows-worker",
        )
        key = _slot_key(host_code, slot)
        with self._lock:
            existing_id = self._slot_to_worker.get(key)
            if existing_id is not None:
                if existing_id in self._revoked_workers:
                    raise AuthorizationError(
                        "Worker assignment revoked",
                        code="worker_revoked",
                        details={"worker_id": str(existing_id), "slot_id": slot},
                    )
                worker = self.plane.provisioner.get(existing_id)  # type: ignore[union-attr]
                if (
                    worker is not None
                    and worker.lifecycle is not WorkerLifecycleState.REVOKED
                ):
                    logger.info(
                        "mt5_worker_register_idempotent worker_id=%s slot=%s",
                        worker.worker_id,
                        slot,
                    )
                    return {"ok": True, "idempotent": True, **self._public(worker)}

            lab_user, lab_acct = lab_ids_for_slot(host_code=host_code, slot_id=slot)
            owner = user_id or lab_user
            account = broker_account_id or lab_acct
            worker = self.plane.provision_worker(
                user_id=owner,
                broker_account_id=account,
                host_id=host.host_id,
            )
            # Bind slot metadata without secrets.
            meta = dict(worker.metadata)
            meta.update(
                {
                    "slot_id": slot,
                    "host_code": host.host_code,
                    "platform": (platform or "windows-local")[:64],
                    "lab_binding": user_id is None,
                }
            )
            worker = self.plane.provisioner.save(  # type: ignore[union-attr]
                _with_metadata(worker, meta)
            )
            self._slot_to_worker[key] = worker.worker_id
            self._worker_to_slot[worker.worker_id] = key
            self._revoked_workers.discard(worker.worker_id)
        logger.info(
            "mt5_worker_registered worker_id=%s host=%s slot=%s",
            worker.worker_id,
            host.host_code,
            slot,
        )
        return {"ok": True, "idempotent": False, **self._public(worker)}

    def require_worker(self, worker_id: UUID) -> WorkerRuntime:
        assert self.plane.provisioner is not None
        worker = self.plane.provisioner.get(worker_id)
        if worker is None:
            raise NotFoundError(
                "Worker not found", details={"worker_id": str(worker_id)}
            )
        if (
            worker.worker_id in self._revoked_workers
            or worker.lifecycle is WorkerLifecycleState.REVOKED
        ):
            raise AuthorizationError(
                "Worker assignment revoked",
                code="worker_revoked",
                details={"worker_id": str(worker_id)},
            )
        return worker

    def get_assignment(self, worker_id: UUID) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        return {
            "ok": True,
            "assignment": self._public(worker),
            "credentials": {
                "authorized": True,
                "password_included": False,
                "note": (
                    "Plaintext passwords are never returned by the control plane. "
                    "Local demo login uses QF_DEMO_* on the Windows host until "
                    "vault unwrap is wired for Connect UI."
                ),
            },
        }

    def heartbeat(
        self,
        *,
        worker_id: UUID,
        slot_id: str | None = None,
        lifecycle: str | None = None,
        ready: bool | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        # Slot binding check when provided.
        if slot_id:
            expected = self._worker_to_slot.get(worker_id, "")
            if expected and not expected.endswith(f"::{slot_id.strip().lower()}"):
                raise AuthorizationError(
                    "Worker is not assigned to this slot",
                    code="slot_mismatch",
                    details={"worker_id": str(worker_id), "slot_id": slot_id},
                )
        updated = self.plane.heartbeat(
            worker_id=worker.worker_id, user_id=worker.user_id, now=now
        )
        # Optional lifecycle hint from agent (non-secret health only).
        if lifecycle and lifecycle != updated.lifecycle.value:
            try:
                target = WorkerLifecycleState(lifecycle)
                if target in {
                    WorkerLifecycleState.STARTING,
                    WorkerLifecycleState.AUTHENTICATING,
                    WorkerLifecycleState.VERIFYING,
                    WorkerLifecycleState.READY,
                    WorkerLifecycleState.DISCONNECTED,
                    WorkerLifecycleState.ERROR,
                    WorkerLifecycleState.RECONNECTING,
                }:
                    # Only apply if transition is valid; otherwise keep heartbeat.
                    with contextlib.suppress(ValidationError):
                        updated = self.plane.provisioner.save(  # type: ignore[union-attr]
                            updated.with_lifecycle(target)
                        )
            except ValueError:
                pass
        _ = ready  # informational; READY still requires verify path
        return {"ok": True, "idempotent": True, **self._public(updated)}

    def report_health(
        self,
        *,
        worker_id: UUID,
        cpu_percent: float = 0.0,
        ram_percent: float = 0.0,
        disk_percent: float = 0.0,
        healthy: bool = True,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        # Host metrics only — strip any accidental secret keys.
        safe_details = {
            k: v
            for k, v in dict(details or {}).items()
            if "password" not in str(k).lower()
            and "secret" not in str(k).lower()
            and "token" not in str(k).lower()
        }
        self.plane.capacity.update_metrics(
            worker.host_id,
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            disk_percent=disk_percent,
            healthy=healthy,
        )
        hb = self.plane.heartbeat(worker_id=worker.worker_id, user_id=worker.user_id)
        return {
            "ok": True,
            **self._public(hb),
            "host_metrics_accepted": True,
            "details_keys": sorted(safe_details.keys()),
        }

    def release(self, *, worker_id: UUID) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        stopped = self.plane.provisioner.stop(  # type: ignore[union-attr]
            worker_id=worker.worker_id, user_id=worker.user_id
        )
        return {"ok": True, **self._public(stopped)}

    def revoke(self, *, worker_id: UUID) -> dict[str, Any]:
        assert self.plane.provisioner is not None
        worker = self.plane.provisioner.get(worker_id)
        if worker is None:
            raise NotFoundError(
                "Worker not found", details={"worker_id": str(worker_id)}
            )
        revoked = self.plane.provisioner.revoke(
            worker_id=worker.worker_id, user_id=worker.user_id
        )
        with self._lock:
            self._revoked_workers.add(worker.worker_id)
            key = self._worker_to_slot.pop(worker.worker_id, None)
            if key:
                self._slot_to_worker.pop(key, None)
        logger.info("mt5_worker_revoked worker_id=%s", worker.worker_id)
        return {"ok": True, **self._public(revoked)}

    def reconnect(self, *, worker_id: UUID) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        assert self.plane.supervisor is not None
        updated, delay = self.plane.supervisor.request_reconnect(
            worker_id=worker.worker_id, user_id=worker.user_id
        )
        return {
            "ok": True,
            "reconnect_backoff_seconds": delay,
            **self._public(updated),
        }

    def scan_stale(self, *, now: datetime | None = None) -> dict[str, Any]:
        stale = self.plane.scan_stale(now=now)
        return {
            "ok": True,
            "stale_count": len(stale),
            "workers": [self._public(w) for w in stale],
        }

    def authorize_credentials(self, *, worker_id: UUID) -> dict[str, Any]:
        """Confirm assignment may access vault later — never returns password."""
        worker = self.require_worker(worker_id)
        return {
            "ok": True,
            "authorized": True,
            "worker_id": str(worker.worker_id),
            "user_id": str(worker.user_id),
            "broker_account_id": str(worker.broker_account_id),
            "password_included": False,
            "login_verified": worker.account_login_verified,
            "server_verified": worker.server_verified,
            "note": "No decrypted credential payload is included in this response.",
        }


def _with_metadata(worker: WorkerRuntime, metadata: dict[str, Any]) -> WorkerRuntime:
    from dataclasses import replace

    from app.domain.multi_account.execution_worker_registry import (
        assert_tenant_safe_worker_metadata,
    )

    return replace(
        worker,
        metadata=assert_tenant_safe_worker_metadata(metadata),
        updated_at=datetime.now(UTC),
    )
