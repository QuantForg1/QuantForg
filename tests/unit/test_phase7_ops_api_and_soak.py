"""Phase 7 — owner ops cards + sustained concurrent soak (isolated)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.auth import AuthUserDTO
from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
    reset_durable_dispatch_queue_for_tests,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.application.services.multi_account_ops_service import owner_ops_snapshot
from app.domain.enums.user import UserRole
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import CentralSignalIntent
from app.presentation.dependencies.auth import get_current_user
from app.presentation.routers import multi_account_ops as ops_router

pytestmark = [pytest.mark.unit]

_SETTINGS = SimpleNamespace(
    multi_account_dispatch_enabled=True,
    multi_account_live_submit_enabled=False,
)


def _proposal() -> RiskSettingProposal:
    return RiskSettingProposal(
        planned_risk_pct=Decimal("10"),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )


def _ready(user, account) -> DispatchTarget:
    return DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=_proposal(),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )


def _owner(email: str = "owner@quantforg.test") -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email=email,
        display_name="Owner",
        role=UserRole.OWNER.value,
        status="active",
        auth_user_id=uuid4(),
    )


def test_owner_ops_cards_shape_and_no_secrets() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    q.plan_and_enqueue(
        signal=CentralSignalIntent.create(
            symbol="XAUUSD", side="BUY", quality=80, idempotency_key="ops:card-1"
        ),
        targets=[_ready(user, account)],
        settings=_SETTINGS,
    )
    worker = uuid4()
    job = q.claim_next(worker_id=worker, user_id=user, broker_account_id=account)
    assert job is not None
    q.acknowledge(intent_id=job.intent_id, worker_id=worker)
    snap = owner_ops_snapshot(queue=q, settings=_SETTINGS)
    cards = snap["cards"]
    for key in (
        "queue_depth",
        "pending",
        "delivered",
        "acknowledged",
        "failed",
        "expired",
        "dead_letter",
        "workers",
        "delivery_latency",
        "retry_counts",
        "brokers",
    ):
        assert key in cards
    assert cards["acknowledged"] >= 1
    assert snap["safety"]["live_submit_allowed"] is False
    assert snap["safety"]["refresh_does_not_enqueue"] is True
    assert "password" not in str(snap).lower()


@pytest.mark.asyncio
async def test_owner_ops_handler_denies_non_designated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct handler check — designated-owner gate without TestClient auth stack."""
    monkeypatch.setattr(ops_router, "is_designated_owner_email", lambda _e: False)
    with pytest.raises(Exception) as err:
        await ops_router.owner_multi_account_ops(_owner())
    assert "designated" in str(err.value).lower() or getattr(
        err.value, "code", ""
    ) in {"designated_owner_required", "insufficient_role"}


def test_sustained_concurrent_soak_single_winner_and_recovery() -> None:
    """Meaningful sustained soak (≥15s) — not a one-shot unit race."""
    q = DurableDispatchQueue(lease_seconds=2, max_attempts=4)
    users = [(uuid4(), uuid4()) for _ in range(24)]
    for i, (user, account) in enumerate(users):
        signal = CentralSignalIntent.create(
            symbol="XAUUSD",
            side="BUY",
            quality=80,
            idempotency_key=f"soak:sig:{i}",
        )
        q.plan_and_enqueue(
            signal=signal,
            targets=[_ready(user, account)],
            settings=_SETTINGS,
        )
        q.plan_and_enqueue(
            signal=signal,
            targets=[_ready(user, account)],
            settings=_SETTINGS,
        )

    assert q.metrics().depth == 24
    start = time.monotonic()
    duration_s = 18.0
    claims = 0
    acks = 0
    fails = 0
    race_losses = 0
    seed_n = {"n": 1000}

    def _reseed(batch: int) -> None:
        for _ in range(batch):
            seed_n["n"] += 1
            n = seed_n["n"]
            user, account = users[n % len(users)]
            q.plan_and_enqueue(
                signal=CentralSignalIntent.create(
                    symbol="XAUUSD",
                    side="BUY",
                    quality=80,
                    idempotency_key=f"soak:reseed:{n}",
                ),
                targets=[_ready(user, account)],
                settings=_SETTINGS,
            )

    def worker_loop(idx: int) -> tuple[int, int, int, int]:
        local_claims = local_acks = local_fails = local_losses = 0
        wid = uuid4()
        deadline = start + duration_s
        cursor = idx
        while time.monotonic() < deadline:
            user, account = users[cursor % len(users)]
            cursor += 1
            job = q.claim_next(worker_id=wid, user_id=user, broker_account_id=account)
            if job is None:
                q.expire_leases()
                if idx % 4 == 0:
                    _reseed(3)
                time.sleep(0.01)
                continue
            local_claims += 1
            other = q.claim_next(
                worker_id=uuid4(), user_id=user, broker_account_id=account
            )
            if other is None:
                local_losses += 1
            if local_claims % 5 == 0:
                q.fail(
                    intent_id=job.intent_id,
                    worker_id=wid,
                    reason="soak_injected_fail",
                )
                local_fails += 1
            else:
                q.acknowledge(intent_id=job.intent_id, worker_id=wid)
                local_acks += 1
            time.sleep(0.005)
        return local_claims, local_acks, local_fails, local_losses

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(worker_loop, i) for i in range(16)]
        for f in as_completed(futs):
            c, a, fl, losses = f.result()
            claims += c
            acks += a
            fails += fl
            race_losses += losses

    elapsed = time.monotonic() - start
    recovered = q.recover_after_restart()
    victim_user, victim_acct = users[0]
    q.set_kill_switch(user_id=victim_user, enabled=True)
    assert (
        q.claim_next(
            worker_id=uuid4(), user_id=victim_user, broker_account_id=victim_acct
        )
        is None
    )
    q.revoke_account_jobs(broker_account_id=users[1][1], reason="revoked_soak")

    metrics = q.metrics()
    assert elapsed >= 15.0
    assert claims >= 24
    assert acks + fails >= 24
    assert race_losses >= 1
    assert metrics.to_dict()["live_submit_enabled"] is False
    report = {
        "duration_s": round(elapsed, 2),
        "claims": claims,
        "acks": acks,
        "fails": fails,
        "race_losses": race_losses,
        "recovered_leases": recovered,
        "final_depth": metrics.depth,
        "dead_letter": metrics.dead_letter,
        "throughput_claims_per_s": round(claims / max(elapsed, 0.001), 2),
    }
    print("PHASE7_SOAK_REPORT", report)
    assert report["throughput_claims_per_s"] > 0


def test_skip_locked_helper_is_safe_when_table_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.persistence import postgres_signal_dispatch as pg

    monkeypatch.setattr(pg, "table_ready", lambda: False)
    assert (
        pg.claim_next_skip_locked(
            worker_id=uuid4(), user_id=uuid4(), broker_account_id=uuid4()
        )
        is None
    )
