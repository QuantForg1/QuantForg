"""Phase 7 — multi-account ops observability (read-only, no LIVE)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import DurableDispatchQueue
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.application.services.multi_account_ops_service import (
    customer_dispatch_status,
    owner_ops_snapshot,
)
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import CentralSignalIntent

pytestmark = [pytest.mark.unit]

_SETTINGS = SimpleNamespace(
    multi_account_dispatch_enabled=True,
    multi_account_live_submit_enabled=False,
)


def test_owner_ops_snapshot_flags_and_metrics() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="signal:ops-1",
    )
    q.plan_and_enqueue(
        signal=signal,
        targets=[
            DispatchTarget(
                user_id=user,
                broker_account_id=account,
                proposal=RiskSettingProposal(
                    planned_risk_pct=Decimal("10"),
                    aggregate_open_risk_pct=Decimal("30"),
                    max_lot=Decimal("0.01"),
                    daily_loss_pct=Decimal("48"),
                    max_concurrent_positions=1,
                ),
                account=AccountReadiness(
                    status="active", ownership_verified=True, user_id=user
                ),
                worker=WorkerReadiness(present=True, ready=True),
            )
        ],
        settings=_SETTINGS,
    )
    snap = owner_ops_snapshot(queue=q, settings=_SETTINGS)
    assert snap["feature_flags"]["MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED"] is False
    assert snap["safety"]["live_submit_allowed"] is False
    assert snap["dispatch_queue"]["depth"] >= 1
    blob = str(snap)
    assert "password" not in blob.lower() or "no password" in blob.lower()


def test_customer_status_is_user_scoped() -> None:
    q = DurableDispatchQueue()
    u1, a1, u2, a2 = uuid4(), uuid4(), uuid4(), uuid4()
    for uid, aid, key in ((u1, a1, "s1"), (u2, a2, "s2")):
        q.plan_and_enqueue(
            signal=CentralSignalIntent.create(
                symbol="XAUUSD",
                side="BUY",
                quality=80,
                idempotency_key=f"signal:{key}",
            ),
            targets=[
                DispatchTarget(
                    user_id=uid,
                    broker_account_id=aid,
                    proposal=RiskSettingProposal(
                        planned_risk_pct=Decimal("10"),
                        aggregate_open_risk_pct=Decimal("30"),
                        max_lot=Decimal("0.01"),
                        daily_loss_pct=Decimal("48"),
                        max_concurrent_positions=1,
                    ),
                    account=AccountReadiness(
                        status="active", ownership_verified=True, user_id=uid
                    ),
                    worker=WorkerReadiness(present=True, ready=True),
                )
            ],
            settings=_SETTINGS,
        )
    mine = customer_dispatch_status(user_id=u1, queue=q)
    assert mine["job_count"] == 1
    assert mine["jobs"][0]["user_id"] == str(u1)
    assert all(j["user_id"] == str(u1) for j in mine["jobs"])
    assert mine["live_submit_allowed"] is False
    assert mine["credentials_exposed"] is False
    assert mine["eligibility"]["live_submit_ready"] is False
    assert mine["eligibility"]["source"] == "feature_gates_and_eligibility_engine"
    assert isinstance(mine["eligibility"]["engine_evaluations"], list)
    assert mine["connection_verification"]["verified"] is False
    assert mine["worker_availability"]["reported"] is False
    other = customer_dispatch_status(user_id=u2, queue=q)
    assert other["job_count"] == 1
    assert other["jobs"][0]["user_id"] == str(u2)
    assert all(j["user_id"] != str(u1) for j in other["jobs"])
