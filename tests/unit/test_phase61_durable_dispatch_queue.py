"""Phase 6.1 — durable dispatch queue: idempotency, claim, recovery, isolation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.domain.multi_account.dispatch_queue import DeliveryStatus
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)

pytestmark = [pytest.mark.unit]

_SETTINGS_ON = SimpleNamespace(
    multi_account_dispatch_enabled=True,
    multi_account_live_submit_enabled=False,
)
_SETTINGS_OFF = SimpleNamespace(
    multi_account_dispatch_enabled=False,
    multi_account_live_submit_enabled=False,
)


def _proposal(pct: str = "10") -> RiskSettingProposal:
    return RiskSettingProposal(
        planned_risk_pct=Decimal(pct),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )


def _signal(key: str = "signal:p61-1") -> CentralSignalIntent:
    return CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key=key,
    )


def _ready_target(user, account) -> DispatchTarget:
    return DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=_proposal(),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )


def test_enqueue_idempotent_and_no_secrets_in_payload() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    signal = _signal()
    plan, jobs = q.plan_and_enqueue(
        signal=signal,
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    assert plan.live_submit_allowed is False
    assert len(jobs) == 1
    assert jobs[0].delivery_status is DeliveryStatus.PENDING
    assert jobs[0].state is AccountExecutionState.QUEUED
    assert "password" not in jobs[0].payload
    # Duplicate signal enqueue must not create a second job.
    _, jobs2 = q.plan_and_enqueue(
        signal=signal,
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    assert jobs2[0].intent_id == jobs[0].intent_id
    assert q.metrics().depth == 1


def test_dispatch_flag_off_does_not_queue_delivery() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:off"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_OFF,
    )
    assert jobs[0].state is AccountExecutionState.ELIGIBLE
    assert jobs[0].delivery_status is DeliveryStatus.NONE
    assert (
        q.claim_next(worker_id=uuid4(), user_id=user, broker_account_id=account) is None
    )


def test_exclusive_claim_and_foreign_worker_denied() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    other_user, other_acct = uuid4(), uuid4()
    worker_a, worker_b = uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:claim"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    claimed = q.claim_next(worker_id=worker_a, user_id=user, broker_account_id=account)
    assert claimed is not None
    assert claimed.delivery_status is DeliveryStatus.CLAIMED
    # Same job cannot be claimed again while leased.
    assert (
        q.claim_next(worker_id=worker_b, user_id=user, broker_account_id=account)
        is None
    )
    # Foreign user/account sees nothing.
    assert (
        q.claim_next(
            worker_id=worker_b, user_id=other_user, broker_account_id=other_acct
        )
        is None
    )
    with pytest.raises(PermissionError):
        q.acknowledge(intent_id=jobs[0].intent_id, worker_id=worker_b)


def test_ack_and_duplicate_signal_no_second_execution_path() -> None:
    q = DurableDispatchQueue()
    user, account, worker = uuid4(), uuid4(), uuid4()
    signal = _signal("signal:ack")
    _, jobs = q.plan_and_enqueue(
        signal=signal,
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    q.claim_next(worker_id=worker, user_id=user, broker_account_id=account)
    acked = q.acknowledge(intent_id=jobs[0].intent_id, worker_id=worker)
    assert acked.delivery_status is DeliveryStatus.ACKED
    assert acked.payload.get("live_submit_allowed") is False
    # Re-enqueue same idempotency → same job, still acked (no re-delivery).
    _, again = q.plan_and_enqueue(
        signal=signal,
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    assert again[0].delivery_status is DeliveryStatus.ACKED
    assert (
        q.claim_next(worker_id=worker, user_id=user, broker_account_id=account) is None
    )


def test_fail_retry_then_dead_letter() -> None:
    q = DurableDispatchQueue(max_attempts=2, lease_seconds=30)
    user, account, worker = uuid4(), uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:fail"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    intent = jobs[0].intent_id
    now = datetime.now(UTC)
    q.claim_next(worker_id=worker, user_id=user, broker_account_id=account, now=now)
    failed = q.fail(intent_id=intent, worker_id=worker, reason="disconnect", now=now)
    assert failed.delivery_status is DeliveryStatus.PENDING
    assert failed.next_retry_at is not None
    # Advance clock past retry.
    later = failed.next_retry_at + timedelta(seconds=1)
    q.claim_next(worker_id=worker, user_id=user, broker_account_id=account, now=later)
    dead = q.fail(intent_id=intent, worker_id=worker, reason="disconnect", now=later)
    assert dead.delivery_status is DeliveryStatus.DEAD_LETTER
    assert dead.state is AccountExecutionState.DEAD_LETTER


def test_stale_lease_expires_and_reclaimable() -> None:
    q = DurableDispatchQueue(lease_seconds=10)
    user, account, worker = uuid4(), uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:lease"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    t0 = datetime.now(UTC)
    q.claim_next(worker_id=worker, user_id=user, broker_account_id=account, now=t0)
    t1 = t0 + timedelta(seconds=11)
    assert q.expire_leases(now=t1) == 1
    reclaimed = q.claim_next(
        worker_id=uuid4(), user_id=user, broker_account_id=account, now=t1
    )
    assert reclaimed is not None
    assert reclaimed.intent_id == jobs[0].intent_id


def test_restart_recovery_releases_claims() -> None:
    q = DurableDispatchQueue()
    user, account, worker = uuid4(), uuid4(), uuid4()
    q.plan_and_enqueue(
        signal=_signal("signal:restart"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    q.claim_next(worker_id=worker, user_id=user, broker_account_id=account)
    snap = q.snapshot()
    restored = DurableDispatchQueue.from_snapshot(snap)
    assert restored.recover_after_restart() == 1
    job = restored.claim_next(
        worker_id=uuid4(), user_id=user, broker_account_id=account
    )
    assert job is not None
    assert job.delivery_status is DeliveryStatus.CLAIMED


def test_revoked_account_cancels_pending() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    q.plan_and_enqueue(
        signal=_signal("signal:revoke"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    n = q.revoke_account_jobs(broker_account_id=account, reason="account_revoked")
    assert n == 1
    assert (
        q.claim_next(worker_id=uuid4(), user_id=user, broker_account_id=account) is None
    )


def test_kill_switch_isolates_one_user() -> None:
    q = DurableDispatchQueue()
    u1, a1, u2, a2 = uuid4(), uuid4(), uuid4(), uuid4()
    q.plan_and_enqueue(
        signal=_signal("signal:ks1"),
        targets=[_ready_target(u1, a1), _ready_target(u2, a2)],
        settings=_SETTINGS_ON,
    )
    q.set_kill_switch(user_id=u1, enabled=True)
    assert q.claim_next(worker_id=uuid4(), user_id=u1, broker_account_id=a1) is None
    other = q.claim_next(worker_id=uuid4(), user_id=u2, broker_account_id=a2)
    assert other is not None
    assert other.user_id == u2


def test_concurrent_claim_single_winner() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    q.plan_and_enqueue(
        signal=_signal("signal:race"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    winners: list = []

    def _try_claim(_: int):
        return q.claim_next(worker_id=uuid4(), user_id=user, broker_account_id=account)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_try_claim, i) for i in range(16)]
        for f in as_completed(futs):
            job = f.result()
            if job is not None:
                winners.append(job.intent_id)
    assert len(winners) == 1


def test_risk_ceiling_blocks_enqueue_delivery() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    target = DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("1.00"),  # exceeds 0.01 Owner ceiling
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        ),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:ceiling"),
        targets=[target],
        settings=_SETTINGS_ON,
    )
    assert jobs[0].state is AccountExecutionState.BLOCKED
    assert (
        q.claim_next(worker_id=uuid4(), user_id=user, broker_account_id=account) is None
    )


def test_public_dict_strips_secret_keys() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:scrub"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    # Inject secret into internal payload then verify public scrub.
    with q._lock:
        q._jobs[jobs[0].idempotency_key].payload["password"] = "nope"
        q._jobs[jobs[0].idempotency_key].payload["token"] = "nope"
    pub = q.get(jobs[0].intent_id)
    assert pub is not None
    assert "password" not in pub.to_public_dict()["payload"]
    assert "token" not in pub.to_public_dict()["payload"]
    assert pub.to_public_dict()["live_submit_allowed"] is False


def test_module_never_imports_order_send() -> None:
    import inspect

    import app.application.services.multi_account_dispatch_queue as mod

    src = inspect.getsource(mod)
    assert "order_send(" not in src
    assert "OMS" not in src or "never" in src.lower()


def test_live_submit_env_true_still_forced_off() -> None:
    """Even if LIVE submit flag is mistakenly True, queue refuses it."""
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    plan, jobs = q.plan_and_enqueue(
        signal=_signal("signal:live-force-off"),
        targets=[_ready_target(user, account)],
        settings=settings,
    )
    assert plan.live_submit_allowed is False
    assert jobs[0].payload.get("live_submit_allowed") is False
    assert q.live_submit_armed() is False


def test_pg_mirror_hooks_are_best_effort_noops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror helpers must not raise when Postgres is unavailable."""
    q = DurableDispatchQueue()
    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("called")
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "app.infrastructure.persistence.postgres_signal_dispatch.upsert_central_signal",
        _boom,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.postgres_signal_dispatch.upsert_intent_job",
        _boom,
    )
    monkeypatch.setattr(
        "app.infrastructure.persistence.postgres_signal_dispatch.record_delivery_event",
        _boom,
    )
    user, account = uuid4(), uuid4()
    _, jobs = q.plan_and_enqueue(
        signal=_signal("signal:mirror"),
        targets=[_ready_target(user, account)],
        settings=_SETTINGS_ON,
    )
    worker = uuid4()
    claimed = q.claim_next(worker_id=worker, user_id=user, broker_account_id=account)
    assert claimed is not None
    q.acknowledge(intent_id=claimed.intent_id, worker_id=worker)
    assert jobs
    assert calls  # hooks attempted
    assert q.get(claimed.intent_id) is not None
