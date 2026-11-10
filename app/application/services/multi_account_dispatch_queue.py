"""Phase 6.1 — durable multi-account dispatch queue (non-executing).

Persists planned intents, supports restart recovery, idempotent enqueue,
and exclusive worker claim/ACK with leases. Never calls OMS / order_send /
MT5 gateway. LIVE submit stays forced off.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from app.application.services.multi_account_dispatch_dry_run import (
    DispatchPlan,
    DispatchTarget,
    plan_signal_dispatch,
)
from app.domain.multi_account.dispatch_queue import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DeliveryStatus,
    DispatchEvent,
    DispatchJob,
    QueueMetrics,
    assert_delivery_transition,
    lease_deadline,
    retry_delay_seconds,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)

_SECRET_KEYS = frozenset(
    {
        "password",
        "token",
        "secret",
        "sealed_credentials",
        "credential",
        "api_key",
        "login_password",
    }
)


def _sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {k: v for k, v in payload.items() if k.lower() not in _SECRET_KEYS}


@dataclass
class DurableDispatchQueue:
    """Process-local durable queue with optional snapshot for restart tests.

    Production may mirror rows via ``postgres_signal_dispatch``; this class is
    the behavioral source of truth for unit tests and in-process recovery.
    """

    lease_seconds: int = DEFAULT_LEASE_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    _lock: Lock = field(default_factory=Lock, repr=False)
    _jobs: dict[str, DispatchJob] = field(default_factory=dict, repr=False)
    _by_id: dict[UUID, str] = field(default_factory=dict, repr=False)
    _events: list[DispatchEvent] = field(default_factory=list, repr=False)
    _signals: dict[str, CentralSignalIntent] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ enqueue
    def enqueue_plan(
        self,
        plan: DispatchPlan,
        *,
        signal: CentralSignalIntent,
        now: datetime | None = None,
    ) -> list[DispatchJob]:
        """Idempotently persist plan items. Blocked items are stored as blocked."""
        ts = now or datetime.now(UTC)
        out: list[DispatchJob] = []
        with self._lock:
            self._signals[signal.idempotency_key] = signal
            for item in plan.items:
                key = item.idempotency_key
                existing = self._jobs.get(key)
                if existing is not None:
                    out.append(deepcopy(existing))
                    continue
                delivery = (
                    DeliveryStatus.PENDING
                    if item.intent.state is AccountExecutionState.QUEUED
                    else DeliveryStatus.NONE
                )
                if item.intent.state is AccountExecutionState.BLOCKED:
                    delivery = DeliveryStatus.NONE
                if item.intent.state is AccountExecutionState.ELIGIBLE:
                    # Dispatch flag off → eligible but not queued for delivery.
                    delivery = DeliveryStatus.NONE
                job = DispatchJob(
                    intent_id=item.intent.execution_id,
                    signal_id=signal.signal_id,
                    user_id=item.intent.user_id,
                    broker_account_id=item.intent.broker_account_id,
                    idempotency_key=key,
                    state=item.intent.state,
                    delivery_status=delivery,
                    block_reason=item.intent.block_reason,
                    max_attempts=self.max_attempts,
                    available_at=ts,
                    payload=_sanitize_payload(
                        {
                            "symbol": signal.symbol,
                            "side": signal.side,
                            "quality": signal.quality,
                            "delivery_suppressed": True,
                            "live_submit_allowed": False,
                            "dispatch_allowed": plan.dispatch_allowed,
                            "effective": item.evaluation.effective,
                        }
                    ),
                    created_at=ts,
                    updated_at=ts,
                )
                self._jobs[key] = job
                self._by_id[job.intent_id] = key
                self._events.append(
                    DispatchEvent.create(
                        intent_id=job.intent_id,
                        user_id=job.user_id,
                        broker_account_id=job.broker_account_id,
                        event_type="enqueued",
                        detail=job.state.value,
                    )
                )
                out.append(deepcopy(job))
        return out

    def plan_and_enqueue(
        self,
        *,
        signal: CentralSignalIntent,
        targets: list[DispatchTarget],
        settings: Any | None = None,
        require_readiness: bool = True,
    ) -> tuple[DispatchPlan, list[DispatchJob]]:
        plan = plan_signal_dispatch(
            signal=signal,
            targets=targets,
            settings=settings,
            require_readiness=require_readiness,
        )
        # Even if env mistakenly enables live submit, queue refuses it.
        if multi_account_live_submit_allowed(settings):
            plan = DispatchPlan(
                signal_id=plan.signal_id,
                signal_idempotency_key=plan.signal_idempotency_key,
                dispatch_allowed=plan.dispatch_allowed,
                live_submit_allowed=False,
                items=plan.items,
                created_at=plan.created_at,
            )
        jobs = self.enqueue_plan(plan, signal=signal)
        return plan, jobs

    # ------------------------------------------------------------------ claim
    def claim_next(
        self,
        *,
        worker_id: UUID,
        user_id: UUID,
        broker_account_id: UUID,
        now: datetime | None = None,
    ) -> DispatchJob | None:
        """Exclusive claim for the worker's assigned account only."""
        ts = now or datetime.now(UTC)
        with self._lock:
            self._expire_leases_unlocked(ts)
            candidates = [
                j
                for j in self._jobs.values()
                if j.user_id == user_id
                and j.broker_account_id == broker_account_id
                and not j.kill_switch
                and j.state is AccountExecutionState.QUEUED
                and j.delivery_status
                in {
                    DeliveryStatus.PENDING,
                    DeliveryStatus.FAILED,
                    DeliveryStatus.EXPIRED,
                }
                and j.available_at <= ts
                and (
                    j.lease_owner_worker_id is None
                    or (j.lease_expires_at is not None and j.lease_expires_at <= ts)
                )
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda j: (j.available_at, j.created_at))
            job = candidates[0]
            assert_delivery_transition(job.delivery_status, DeliveryStatus.CLAIMED)
            job.delivery_status = DeliveryStatus.CLAIMED
            job.lease_owner_worker_id = worker_id
            job.lease_expires_at = lease_deadline(now=ts, seconds=self.lease_seconds)
            job.attempt_count += 1
            job.updated_at = ts
            self._events.append(
                DispatchEvent.create(
                    intent_id=job.intent_id,
                    user_id=job.user_id,
                    broker_account_id=job.broker_account_id,
                    worker_id=worker_id,
                    event_type="claimed",
                    detail=f"attempt={job.attempt_count}",
                )
            )
            return deepcopy(job)

    def mark_delivered(
        self,
        *,
        intent_id: UUID,
        worker_id: UUID,
        now: datetime | None = None,
    ) -> DispatchJob:
        return self._mutate_claimed(
            intent_id=intent_id,
            worker_id=worker_id,
            new_status=DeliveryStatus.DELIVERED,
            event_type="delivered",
            now=now,
            set_delivered=True,
        )

    def acknowledge(
        self,
        *,
        intent_id: UUID,
        worker_id: UUID,
        now: datetime | None = None,
        detail: str = "",
    ) -> DispatchJob:
        """Worker ACK of delivery (not broker fill). Never triggers order_send."""
        ts = now or datetime.now(UTC)
        with self._lock:
            job = self._require_leased(intent_id, worker_id, ts)
            # Allow ACK from claimed or delivered.
            if job.delivery_status is DeliveryStatus.CLAIMED:
                assert_delivery_transition(
                    job.delivery_status, DeliveryStatus.DELIVERED
                )
                job.delivery_status = DeliveryStatus.DELIVERED
                job.delivered_at = ts
            assert_delivery_transition(job.delivery_status, DeliveryStatus.ACKED)
            job.delivery_status = DeliveryStatus.ACKED
            job.acked_at = ts
            job.lease_owner_worker_id = worker_id
            job.lease_expires_at = None
            job.updated_at = ts
            if detail:
                job.last_error = ""
            self._events.append(
                DispatchEvent.create(
                    intent_id=job.intent_id,
                    user_id=job.user_id,
                    broker_account_id=job.broker_account_id,
                    worker_id=worker_id,
                    event_type="acked",
                    detail=detail or "delivery_ack",
                )
            )
            return deepcopy(job)

    def fail(
        self,
        *,
        intent_id: UUID,
        worker_id: UUID,
        reason: str,
        now: datetime | None = None,
    ) -> DispatchJob:
        ts = now or datetime.now(UTC)
        with self._lock:
            job = self._require_leased(intent_id, worker_id, ts)
            assert_delivery_transition(job.delivery_status, DeliveryStatus.FAILED)
            job.delivery_status = DeliveryStatus.FAILED
            job.last_error = (reason or "failed")[:500]
            job.lease_owner_worker_id = None
            job.lease_expires_at = None
            job.updated_at = ts
            if job.attempt_count >= job.max_attempts:
                assert_delivery_transition(
                    job.delivery_status, DeliveryStatus.DEAD_LETTER
                )
                job.delivery_status = DeliveryStatus.DEAD_LETTER
                job.state = AccountExecutionState.DEAD_LETTER
                event = "dead_letter"
            else:
                delay = retry_delay_seconds(job.attempt_count)
                job.next_retry_at = ts + timedelta(seconds=delay)
                job.available_at = job.next_retry_at
                assert_delivery_transition(
                    DeliveryStatus.FAILED, DeliveryStatus.PENDING
                )
                job.delivery_status = DeliveryStatus.PENDING
                event = "failed"
            self._events.append(
                DispatchEvent.create(
                    intent_id=job.intent_id,
                    user_id=job.user_id,
                    broker_account_id=job.broker_account_id,
                    worker_id=worker_id,
                    event_type=event,
                    detail=job.last_error,
                )
            )
            return deepcopy(job)

    def cancel(
        self,
        *,
        intent_id: UUID,
        reason: str = "cancelled",
        now: datetime | None = None,
    ) -> DispatchJob:
        ts = now or datetime.now(UTC)
        with self._lock:
            key = self._by_id.get(intent_id)
            if key is None:
                raise KeyError("intent_not_found")
            job = self._jobs[key]
            if job.delivery_status not in {
                DeliveryStatus.ACKED,
                DeliveryStatus.DEAD_LETTER,
                DeliveryStatus.CANCELLED,
            }:
                assert_delivery_transition(
                    job.delivery_status, DeliveryStatus.CANCELLED
                )
            job.delivery_status = DeliveryStatus.CANCELLED
            job.state = AccountExecutionState.CANCELLED
            job.last_error = reason[:500]
            job.lease_owner_worker_id = None
            job.lease_expires_at = None
            job.updated_at = ts
            self._events.append(
                DispatchEvent.create(
                    intent_id=job.intent_id,
                    user_id=job.user_id,
                    broker_account_id=job.broker_account_id,
                    event_type="cancelled",
                    detail=reason,
                )
            )
            return deepcopy(job)

    def set_kill_switch(self, *, user_id: UUID, enabled: bool) -> int:
        """Block new claims for a user; does not affect other users."""
        n = 0
        with self._lock:
            for job in self._jobs.values():
                if job.user_id != user_id:
                    continue
                job.kill_switch = bool(enabled)
                job.updated_at = datetime.now(UTC)
                n += 1
        return n

    def revoke_account_jobs(self, *, broker_account_id: UUID, reason: str) -> int:
        n = 0
        with self._lock:
            for job in self._jobs.values():
                if job.broker_account_id != broker_account_id:
                    continue
                if job.delivery_status in {
                    DeliveryStatus.ACKED,
                    DeliveryStatus.CANCELLED,
                    DeliveryStatus.DEAD_LETTER,
                }:
                    continue
                job.state = AccountExecutionState.BLOCKED
                job.block_reason = reason
                job.delivery_status = DeliveryStatus.CANCELLED
                job.lease_owner_worker_id = None
                job.lease_expires_at = None
                job.updated_at = datetime.now(UTC)
                n += 1
                self._events.append(
                    DispatchEvent.create(
                        intent_id=job.intent_id,
                        user_id=job.user_id,
                        broker_account_id=job.broker_account_id,
                        event_type="cancelled",
                        detail=reason,
                    )
                )
        return n

    def expire_leases(self, *, now: datetime | None = None) -> int:
        ts = now or datetime.now(UTC)
        with self._lock:
            return self._expire_leases_unlocked(ts)

    def recover_after_restart(self, *, now: datetime | None = None) -> int:
        """Release claimed leases so pending work can be reclaimed."""
        ts = now or datetime.now(UTC)
        recovered = 0
        with self._lock:
            for job in self._jobs.values():
                if job.delivery_status is DeliveryStatus.CLAIMED:
                    job.delivery_status = DeliveryStatus.PENDING
                    job.lease_owner_worker_id = None
                    job.lease_expires_at = None
                    job.available_at = ts
                    job.updated_at = ts
                    recovered += 1
                    self._events.append(
                        DispatchEvent.create(
                            intent_id=job.intent_id,
                            user_id=job.user_id,
                            broker_account_id=job.broker_account_id,
                            event_type="restart_recovered",
                            detail="lease_released",
                        )
                    )
        return recovered

    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot for restart tests (no secrets)."""
        with self._lock:
            return {
                "jobs": [j.to_public_dict() for j in self._jobs.values()],
                "events": [
                    {
                        "event_id": str(e.event_id),
                        "intent_id": str(e.intent_id),
                        "user_id": str(e.user_id),
                        "broker_account_id": str(e.broker_account_id),
                        "worker_id": str(e.worker_id) if e.worker_id else None,
                        "event_type": e.event_type,
                        "detail": e.detail,
                    }
                    for e in self._events
                ],
            }

    @classmethod
    def from_snapshot(
        cls, data: dict[str, Any], *, lease_seconds: int = DEFAULT_LEASE_SECONDS
    ) -> DurableDispatchQueue:
        q = cls(lease_seconds=lease_seconds)
        for raw in data.get("jobs") or []:
            job = DispatchJob(
                intent_id=UUID(raw["intent_id"]),
                signal_id=UUID(raw["signal_id"]),
                user_id=UUID(raw["user_id"]),
                broker_account_id=UUID(raw["broker_account_id"]),
                idempotency_key=raw["idempotency_key"],
                state=AccountExecutionState(raw["state"]),
                delivery_status=DeliveryStatus(raw["delivery_status"]),
                block_reason=raw.get("block_reason"),
                attempt_count=int(raw.get("attempt_count") or 0),
                max_attempts=int(raw.get("max_attempts") or DEFAULT_MAX_ATTEMPTS),
                lease_owner_worker_id=(
                    UUID(raw["lease_owner_worker_id"])
                    if raw.get("lease_owner_worker_id")
                    else None
                ),
                lease_expires_at=(
                    datetime.fromisoformat(raw["lease_expires_at"])
                    if raw.get("lease_expires_at")
                    else None
                ),
                available_at=datetime.fromisoformat(raw["available_at"]),
                kill_switch=bool(raw.get("kill_switch")),
                last_error=str(raw.get("last_error") or ""),
                payload=_sanitize_payload(raw.get("payload") or {}),
            )
            q._jobs[job.idempotency_key] = job
            q._by_id[job.intent_id] = job.idempotency_key
        return q

    def get(self, intent_id: UUID) -> DispatchJob | None:
        with self._lock:
            key = self._by_id.get(intent_id)
            return deepcopy(self._jobs[key]) if key else None

    def get_by_idempotency(self, key: str) -> DispatchJob | None:
        with self._lock:
            job = self._jobs.get(key)
            return deepcopy(job) if job else None

    def list_for_user(self, user_id: UUID) -> list[DispatchJob]:
        with self._lock:
            return [deepcopy(j) for j in self._jobs.values() if j.user_id == user_id]

    def events_for_user(self, user_id: UUID) -> list[DispatchEvent]:
        with self._lock:
            return [e for e in self._events if e.user_id == user_id]

    def metrics(self) -> QueueMetrics:
        with self._lock:
            by_d: dict[str, int] = {}
            by_s: dict[str, int] = {}
            claimed = failed = dead = expired = kill = 0
            depth = 0
            for j in self._jobs.values():
                by_d[j.delivery_status.value] = by_d.get(j.delivery_status.value, 0) + 1
                by_s[j.state.value] = by_s.get(j.state.value, 0) + 1
                if j.delivery_status is DeliveryStatus.CLAIMED:
                    claimed += 1
                if j.delivery_status is DeliveryStatus.FAILED:
                    failed += 1
                if j.delivery_status is DeliveryStatus.DEAD_LETTER:
                    dead += 1
                if j.delivery_status is DeliveryStatus.EXPIRED:
                    expired += 1
                if j.kill_switch:
                    kill += 1
                if (
                    j.state is AccountExecutionState.QUEUED
                    and j.delivery_status
                    in {
                        DeliveryStatus.PENDING,
                        DeliveryStatus.FAILED,
                        DeliveryStatus.EXPIRED,
                    }
                    and not j.kill_switch
                ):
                    depth += 1
            return QueueMetrics(
                depth=depth,
                by_delivery_status=by_d,
                by_execution_state=by_s,
                claimed=claimed,
                failed=failed,
                dead_letter=dead,
                expired_leases=expired,
                kill_switched=kill,
            )

    def live_submit_armed(self) -> bool:
        return False

    def dispatch_flag(self, settings: Any | None = None) -> bool:
        return multi_account_dispatch_allowed(settings)

    # ------------------------------------------------------------------ private
    def _require_leased(
        self, intent_id: UUID, worker_id: UUID, ts: datetime
    ) -> DispatchJob:
        key = self._by_id.get(intent_id)
        if key is None:
            raise KeyError("intent_not_found")
        job = self._jobs[key]
        if job.lease_owner_worker_id != worker_id:
            raise PermissionError("lease_owner_mismatch")
        if job.lease_expires_at is not None and job.lease_expires_at < ts:
            raise TimeoutError("lease_expired")
        return job

    def _mutate_claimed(
        self,
        *,
        intent_id: UUID,
        worker_id: UUID,
        new_status: DeliveryStatus,
        event_type: str,
        now: datetime | None,
        set_delivered: bool = False,
    ) -> DispatchJob:
        ts = now or datetime.now(UTC)
        with self._lock:
            job = self._require_leased(intent_id, worker_id, ts)
            assert_delivery_transition(job.delivery_status, new_status)
            job.delivery_status = new_status
            if set_delivered:
                job.delivered_at = ts
            job.updated_at = ts
            self._events.append(
                DispatchEvent.create(
                    intent_id=job.intent_id,
                    user_id=job.user_id,
                    broker_account_id=job.broker_account_id,
                    worker_id=worker_id,
                    event_type=event_type,
                )
            )
            return deepcopy(job)

    def _expire_leases_unlocked(self, ts: datetime) -> int:
        n = 0
        for job in self._jobs.values():
            if (
                job.delivery_status is DeliveryStatus.CLAIMED
                and job.lease_expires_at is not None
                and job.lease_expires_at <= ts
            ):
                assert_delivery_transition(job.delivery_status, DeliveryStatus.EXPIRED)
                job.delivery_status = DeliveryStatus.EXPIRED
                job.lease_owner_worker_id = None
                job.lease_expires_at = None
                job.available_at = ts
                job.updated_at = ts
                # Re-queue for retry unless maxed.
                if job.attempt_count >= job.max_attempts:
                    job.delivery_status = DeliveryStatus.DEAD_LETTER
                    job.state = AccountExecutionState.DEAD_LETTER
                    et = "dead_letter"
                else:
                    assert_delivery_transition(
                        DeliveryStatus.EXPIRED, DeliveryStatus.PENDING
                    )
                    job.delivery_status = DeliveryStatus.PENDING
                    et = "expired"
                self._events.append(
                    DispatchEvent.create(
                        intent_id=job.intent_id,
                        user_id=job.user_id,
                        broker_account_id=job.broker_account_id,
                        event_type=et,
                        detail="lease_expired",
                    )
                )
                n += 1
        return n


# Process singleton for API wiring (tests may replace).
_QUEUE: DurableDispatchQueue | None = None
_QUEUE_LOCK = Lock()


def get_durable_dispatch_queue() -> DurableDispatchQueue:
    global _QUEUE
    with _QUEUE_LOCK:
        if _QUEUE is None:
            _QUEUE = DurableDispatchQueue()
        return _QUEUE


def reset_durable_dispatch_queue_for_tests() -> None:
    global _QUEUE
    with _QUEUE_LOCK:
        _QUEUE = DurableDispatchQueue()


def new_intent_id() -> UUID:
    return uuid4()
