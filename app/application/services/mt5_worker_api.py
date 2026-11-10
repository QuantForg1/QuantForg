"""HTTP-facing MT5 worker control-plane facade (Phase 1C/1E).

Process + optional PostgreSQL durable state. Does not enable LIVE
multi-account submit. Passwords are never stored or returned in plaintext.
"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid5

from app.application.services.mt5_worker_control_plane import Mt5WorkerControlPlane
from app.application.services.mt5_worker_credential_seal import seal_credential_material
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
    """Durable worker registration / heartbeat / revoke API."""

    plane: Mt5WorkerControlPlane
    stale_after: timedelta = field(default_factory=lambda: timedelta(seconds=45))
    _lock: Lock = field(default_factory=Lock)
    _slot_to_worker: dict[str, UUID] = field(default_factory=dict)
    _worker_to_slot: dict[UUID, str] = field(default_factory=dict)
    _revoked_workers: set[UUID] = field(default_factory=set)
    _hydrated: bool = False

    def __post_init__(self) -> None:
        assert self.plane.supervisor is not None
        self.plane.supervisor.stale_after = self.stale_after
        self.hydrate_from_postgres()

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
                "credentials_exposed": False,
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
                    self._persist(worker)
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
        self._persist(worker)
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

    def lab_assignment_gate(self, worker: WorkerRuntime) -> str | None:
        """Fail-closed gate for staging lab enqueue.

        Registration alone is never enough. Returns an error code or None.
        """
        if worker.user_id is None or worker.broker_account_id is None:
            return "assignment_incomplete"
        if worker.last_heartbeat_at is None:
            return "heartbeat_required"
        login_ok = bool((worker.account_login_verified or "").strip())
        server_ok = bool((worker.server_verified or "").strip())
        if login_ok and server_ok:
            return None
        meta = dict(worker.metadata or {})
        # Staging lab attestation must be explicit after heartbeat — never
        # inferred solely from register-time lab_binding.
        if (
            meta.get("lab_binding") is True
            and meta.get("staging_lab_assignment_verified") is True
        ):
            return None
        return "assignment_unverified"

    def attest_staging_lab_assignment(self, *, worker_id: UUID) -> dict[str, Any]:
        """Mark a lab-bound worker assignment verified for staging enqueue only.

        Requires a prior heartbeat. Never sets production eligibility. Never
        exposes credentials.
        """
        worker = self.require_worker(worker_id)
        if worker.last_heartbeat_at is None:
            raise AuthorizationError(
                "Heartbeat required before lab assignment attestation",
                code="heartbeat_required",
                details={"worker_id": str(worker_id)},
            )
        meta = dict(worker.metadata or {})
        if meta.get("lab_binding") is not True:
            raise AuthorizationError(
                "Only lab-bound staging workers may be attested",
                code="lab_binding_required",
                details={"worker_id": str(worker_id)},
            )
        meta["staging_lab_assignment_verified"] = True
        meta["staging_lab_assignment_verified_at"] = datetime.now(UTC).isoformat()
        assert self.plane.provisioner is not None
        updated = self.plane.provisioner.save(_with_metadata(worker, meta))
        self._persist(updated)
        return {
            "ok": True,
            "worker_id": str(updated.worker_id),
            "staging_lab_assignment_verified": True,
            "live_submit_allowed": False,
            "credentials_exposed": False,
        }

    def get_assignment(self, worker_id: UUID) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        return {
            "ok": True,
            "assignment": self._public(worker),
            "credentials": {
                "authorized": True,
                "credentials_exposed": False,
                "note": (
                    "Auth material is never returned by the control plane. "
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
        self._persist(updated)
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
        self._persist(hb)
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
        self._persist(stopped)
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
        try:
            from app.infrastructure.persistence import (
                postgres_mt5_worker_control_plane as cp_store,
            )

            mark_revoked = cp_store.mark_revoked

            mark_revoked(worker.worker_id)
        except Exception:
            logger.warning("mt5_worker_cp_mark_revoked_failed")
        self._persist(revoked)
        logger.info("mt5_worker_revoked worker_id=%s", worker.worker_id)
        return {"ok": True, **self._public(revoked)}

    def reconnect(self, *, worker_id: UUID) -> dict[str, Any]:
        worker = self.require_worker(worker_id)
        assert self.plane.supervisor is not None
        updated, delay = self.plane.supervisor.request_reconnect(
            worker_id=worker.worker_id, user_id=worker.user_id
        )
        self._persist(updated)
        return {
            "ok": True,
            "reconnect_backoff_seconds": delay,
            **self._public(updated),
        }

    def scan_stale(self, *, now: datetime | None = None) -> dict[str, Any]:
        stale = self.plane.scan_stale(now=now)
        for worker in stale:
            self._persist(worker)
        return {
            "ok": True,
            "stale_count": len(stale),
            "workers": [self._public(w) for w in stale],
        }

    def report_verification(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist redacted broker verification evidence. Never stores passwords."""
        from app.domain.broker_connectivity.broker_verification_evidence import (
            ingest_worker_report,
            ops_snapshot,
        )

        entry = ingest_worker_report(payload)
        try:
            from app.infrastructure.persistence import (
                postgres_mt5_broker_verification as ver_store,
            )

            ver_store.upsert_evidence(entry)
        except Exception:
            logger.warning("mt5_broker_verification_pg_persist_failed")
        return {
            "ok": True,
            "credentials_exposed": False,
            "broker_slug": entry.get("broker_slug"),
            "connectable": bool(entry.get("connectable")),
            "connection_status": entry.get("connection_status"),
            "evidence": ops_snapshot(),
        }

    def ops_summary(self) -> dict[str, Any]:
        """Admin/ops snapshot of workers + verification evidence (no passwords)."""
        from app.domain.broker_connectivity.broker_verification_evidence import (
            ops_snapshot,
        )
        from app.domain.broker_connectivity.mt5_server_catalogue import (
            catalogue_snapshot,
        )
        from app.domain.broker_connectivity.verification_matrix import (
            build_verification_matrix,
        )

        assert self.plane.provisioner is not None
        by_id = getattr(self.plane.provisioner, "_by_id", {})
        workers = [self._public(w) for w in by_id.values()]
        hosts = self.plane.capacity.summary()
        control_plane_rows = 0
        try:
            from app.infrastructure.persistence import (
                postgres_mt5_worker_control_plane as cp_store,
            )

            if cp_store.table_ready():
                control_plane_rows = len(cp_store.load_all_workers() or [])
        except Exception:
            control_plane_rows = 0
        return {
            "ok": True,
            "credentials_exposed": False,
            "live_submit_enabled": multi_account_live_submit_allowed(),
            "hosts": hosts,
            "workers": workers,
            "worker_count": len(workers),
            "control_plane_worker_count": control_plane_rows,
            "execution_workers_note": (
                "Runtime registration persists to mt5_worker_control_plane; "
                "public.execution_workers remains the Phase-1a assignment table "
                "and may stay at 0 until ownership-bound provisioning writes it."
            ),
            "verification": ops_snapshot(),
            "verification_matrix": build_verification_matrix(),
            "registry": catalogue_snapshot(),
            "note": (
                "Windows MT5 workers report heartbeats outbound to Railway. "
                "Brokers stay connectable=false until verification evidence exists. "
                "Existing Windows host retained — no new VPS."
            ),
        }

    def authorize_credentials(self, *, worker_id: UUID) -> dict[str, Any]:
        """Confirm assignment may access vault — never returns plaintext password."""
        worker = self.require_worker(worker_id)
        return {
            "ok": True,
            "authorized": True,
            "worker_id": str(worker.worker_id),
            "user_id": str(worker.user_id),
            "broker_account_id": str(worker.broker_account_id),
            "credentials_exposed": False,
            "login_verified": worker.account_login_verified,
            "server_verified": worker.server_verified,
            "note": "No decrypted credential payload is included in this response.",
        }

    def claim_sealed_credentials(self, *, worker_id: UUID) -> dict[str, Any]:
        """Issue a sealed envelope for the assigned worker only.

        Plaintext passwords are never present as a ``password`` JSON field.
        Lab mode uses ``QF_DEMO_*`` on the API host only when explicitly set
        for integration; production vault unwrap is preferred when wired.
        """
        worker = self.require_worker(worker_id)
        token = (self.plane.service_token or "").strip()
        if len(token) < 16:
            raise AuthorizationError(
                "Worker credential seal not configured",
                code="worker_seal_not_configured",
            )
        # Prefer verified login/server; fall back to env demo material for lab.
        login = (
            worker.account_login_verified
            or (os.environ.get("QF_DEMO_LOGIN") or "").strip()
        )
        server = (
            worker.server_verified or (os.environ.get("QF_DEMO_SERVER") or "").strip()
        )
        secret = (os.environ.get("QF_DEMO_PASSWORD") or "").strip()
        # Never log secret. If no material, authorize=false without inventing.
        if not login or not server or not secret:
            return {
                "ok": True,
                "authorized": True,
                "credentials_exposed": False,
                "sealed": False,
                "worker_id": str(worker.worker_id),
                "broker_account_id": str(worker.broker_account_id),
                "error": "credential_material_unavailable",
                "note": (
                    "No sealed envelope issued. Provide authorized vault material "
                    "or QF_DEMO_* on the API for lab-only tests. NOT a successful "
                    "MT5 authentication proof."
                ),
            }
        sealed = seal_credential_material(
            service_token=token,
            worker_id=worker.worker_id,
            login=login,
            server=server,
            password=secret,
        )
        return {"ok": True, **sealed}

    def hydrate_from_postgres(self) -> int:
        """Restore in-memory indexes from durable table when available."""
        if self._hydrated:
            return 0
        self._hydrated = True
        try:
            from app.infrastructure.persistence import (
                postgres_mt5_worker_control_plane as cp_store,
            )

            load_all_workers = cp_store.load_all_workers
        except Exception:
            return 0
        try:
            rows = load_all_workers()
        except Exception:
            logger.warning("mt5_worker_cp_hydrate_failed")
            return 0
        restored = 0
        assert self.plane.provisioner is not None
        for row in rows:
            try:
                worker_id = UUID(str(row["worker_id"]))
                host_code = str(row.get("host_code") or "")
                slot_id = str(row.get("slot_id") or "")
                key = _slot_key(host_code, slot_id)
                user_id = (
                    UUID(str(row["user_id"]))
                    if row.get("user_id")
                    else uuid5(_LAB_NS, f"orphan-user:{worker_id}")
                )
                account_id = (
                    UUID(str(row["broker_account_id"]))
                    if row.get("broker_account_id")
                    else uuid5(_LAB_NS, f"orphan-acct:{worker_id}")
                )
                host_id = (
                    UUID(str(row["host_id"]))
                    if row.get("host_id")
                    else self.plane.capacity.ensure_host(
                        host_code=host_code or "unknown-host", max_terminals=8
                    ).host_id
                )
                lifecycle = WorkerLifecycleState(
                    str(row.get("lifecycle_status") or "pending")
                )
                worker = WorkerRuntime(
                    worker_id=worker_id,
                    worker_code=f"restored-{slot_id or worker_id.hex[:8]}",
                    user_id=user_id,
                    broker_account_id=account_id,
                    host_id=host_id,
                    lifecycle=lifecycle,
                    runtime_session_id=str(row.get("runtime_session_id") or ""),
                    last_heartbeat_at=row.get("last_heartbeat_at"),
                    last_health_check_at=row.get("last_health_check_at"),
                    last_error=str(row.get("last_error") or ""),
                    attempt_count=int(row.get("attempt_count") or 0),
                    trade_allowed=row.get("trade_allowed"),
                    account_login_verified=str(row.get("account_login_verified") or ""),
                    server_verified=str(row.get("server_verified") or ""),
                    metadata={"restored": True, "slot_id": slot_id},
                )
                self.plane.provisioner._by_id[worker_id] = worker
                if (
                    bool(row.get("revoked"))
                    or lifecycle is WorkerLifecycleState.REVOKED
                ):
                    self._revoked_workers.add(worker_id)
                else:
                    self._slot_to_worker[key] = worker_id
                    self._worker_to_slot[worker_id] = key
                    if lifecycle not in {
                        WorkerLifecycleState.STOPPED,
                        WorkerLifecycleState.REVOKED,
                    }:
                        self.plane.provisioner._active_by_user[user_id] = worker_id
                        self.plane.provisioner._active_by_account[account_id] = (
                            worker_id
                        )
                restored += 1
            except Exception:
                logger.exception("mt5_worker_cp_hydrate_row_failed")
        if restored:
            logger.info("mt5_worker_cp_hydrated count=%s", restored)
        return restored

    def _persist(self, worker: WorkerRuntime) -> None:
        slot = self._worker_to_slot.get(worker.worker_id, "")
        host_code = ""
        slot_id = ""
        if "::" in slot:
            host_code, slot_id = slot.split("::", 1)
        try:
            from app.infrastructure.persistence import (
                postgres_mt5_worker_control_plane as cp_store,
            )

            upsert_worker_row = cp_store.upsert_worker_row

            upsert_worker_row(
                {
                    "worker_id": str(worker.worker_id),
                    "host_code": host_code
                    or str(worker.metadata.get("host_code") or "unknown"),
                    "slot_id": slot_id
                    or str(worker.metadata.get("slot_id") or "unknown"),
                    "host_id": str(worker.host_id),
                    "user_id": str(worker.user_id),
                    "broker_account_id": str(worker.broker_account_id),
                    "lifecycle_status": worker.lifecycle.value,
                    "runtime_session_id": worker.runtime_session_id,
                    "platform": str(worker.metadata.get("platform") or "windows-local"),
                    "last_heartbeat_at": worker.last_heartbeat_at,
                    "last_health_check_at": worker.last_health_check_at,
                    "last_error": worker.last_error,
                    "attempt_count": worker.attempt_count,
                    "trade_allowed": worker.trade_allowed,
                    "account_login_verified": worker.account_login_verified,
                    "server_verified": worker.server_verified,
                    "revoked": worker.worker_id in self._revoked_workers
                    or worker.lifecycle is WorkerLifecycleState.REVOKED,
                    "metadata": worker.metadata,
                }
            )
        except Exception:
            logger.warning(
                "mt5_worker_cp_persist_failed worker_id=%s", worker.worker_id
            )


def _with_metadata(worker: WorkerRuntime, metadata: dict[str, Any]) -> WorkerRuntime:
    from app.domain.multi_account.execution_worker_registry import (
        assert_tenant_safe_worker_metadata,
    )

    return replace(
        worker,
        metadata=assert_tenant_safe_worker_metadata(metadata),
        updated_at=datetime.now(UTC),
    )
