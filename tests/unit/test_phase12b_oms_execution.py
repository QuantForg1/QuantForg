"""Phase 12B — multi-account OMS authorize + reconcile (no LIVE money)."""

from __future__ import annotations

from datetime import UTC, datetime
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
from app.application.services.multi_account_oms_execution import (
    authorize_worker_execution,
    multi_account_oms_live_order_send_allowed,
    parse_broker_execution_report,
)
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)
from app.domain.multi_account.worker_runtime import (
    WorkerLifecycleState,
    WorkerRuntime,
)

pytestmark = [pytest.mark.unit]


def _worker(*, ready: bool = True) -> WorkerRuntime:
    now = datetime.now(UTC)
    return WorkerRuntime(
        worker_id=uuid4(),
        worker_code="demo-a",
        user_id=uuid4(),
        broker_account_id=uuid4(),
        host_id=uuid4(),
        lifecycle=WorkerLifecycleState.READY if ready else WorkerLifecycleState.ERROR,
        last_heartbeat_at=now,
        account_login_verified="123456",
        server_verified="XMGlobal-MT5 2",
        trade_allowed=True,
    )


def test_demo_authorize_allows_order_send_when_ready() -> None:
    w = _worker(ready=True)
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
        multi_account_oms_live_order_send_enabled=False,
    )
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.01",
            "stop_loss": "3990",
            "account_environment": "demo",
        },
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k1",
        account_environment="demo",
        settings=settings,
    )
    assert auth.ok is True
    assert auth.order_send_allowed is True
    assert auth.to_public_dict()["order_send"] is False
    assert "password" not in str(auth.to_public_dict()).lower()


def test_live_path_authorize_fail_closed_for_order_send() -> None:
    w = _worker(ready=True)
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
        multi_account_oms_live_order_send_enabled=False,
    )
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.01",
            "stop_loss": "3990",
        },
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k2",
        account_environment="live",
        settings=settings,
    )
    assert auth.ok is True
    assert auth.live_path_authorized is True
    assert auth.order_send_allowed is False
    assert "live_order_send_fail_closed" in auth.reasons
    assert multi_account_oms_live_order_send_allowed(settings) is False


def test_ownership_mismatch_blocks() -> None:
    w = _worker(ready=True)
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
        multi_account_oms_live_order_send_enabled=False,
    )
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.01",
            "stop_loss": "3990",
        },
        job_user_id=uuid4(),
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k3",
        account_environment="demo",
        settings=settings,
    )
    assert auth.ok is False
    assert auth.order_send_allowed is False
    assert "user_ownership_mismatch" in auth.reasons


def test_record_broker_execution_idempotent_and_not_ack() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="sig:12b-1",
        metadata={"volume": "0.01", "account_environment": "demo"},
    )
    target = DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("5"),
            aggregate_open_risk_pct=Decimal("9"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("25"),
            max_concurrent_positions=1,
        ),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    _plan, jobs = q.plan_and_enqueue(signal=signal, targets=[target], settings=settings)
    assert jobs
    worker_id = uuid4()
    claimed = q.claim_next(worker_id=worker_id, user_id=user, broker_account_id=account)
    assert claimed is not None
    filled = q.record_broker_execution(
        intent_id=claimed.intent_id,
        worker_id=worker_id,
        ok=True,
        retcode=10009,
        order_ticket=555,
        deal_ticket=777,
        detail="done",
        broker_payload={"symbol": "XAUUSD", "side": "BUY", "volume": "0.01"},
    )
    assert filled.state is AccountExecutionState.FILLED
    assert filled.payload.get("order_ticket") == 555
    again = q.record_broker_execution(
        intent_id=claimed.intent_id,
        worker_id=worker_id,
        ok=True,
        retcode=10009,
        order_ticket=555,
        deal_ticket=777,
        detail="retry",
    )
    assert again.state is AccountExecutionState.FILLED
    assert again.payload.get("order_ticket") == 555


def test_parse_broker_report_strips_secrets() -> None:
    report = parse_broker_execution_report(
        intent_id=uuid4(),
        worker_id=uuid4(),
        body={
            "ok": True,
            "retcode": 10009,
            "order_ticket": 1,
            "password": "secret",
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.01",
        },
    )
    assert report.ok is True
    assert "password" not in report.raw_safe


def test_revoked_and_disabled_customer_block_send() -> None:
    w = _worker(ready=True)
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
        multi_account_oms_live_order_send_enabled=False,
    )
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload={
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": "0.01",
            "stop_loss": "3990",
            "account_environment": "demo",
        },
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k4",
        revoked=True,
        customer_trading_enabled=False,
        account_environment="demo",
        settings=settings,
    )
    assert auth.ok is False
    assert auth.order_send_allowed is False
    assert "account_revoked" in auth.reasons
    assert "customer_trading_disabled" in auth.reasons


def test_uncertain_order_send_is_unknown_not_retryable() -> None:
    from app.application.services.multi_account_oms_execution import (
        classify_broker_execution_outcome,
    )

    assert (
        classify_broker_execution_outcome(
            ok=False,
            retcode=None,
            order_ticket=None,
            detail="order_send_null",
            uncertain_flag=True,
        )
        == "unknown"
    )
    assert (
        classify_broker_execution_outcome(
            ok=False,
            retcode=None,
            order_ticket=None,
            detail="symbol_select_failed",
            order_send_attempted=False,
        )
        == "rejected"
    )
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="sig:12b-uncertain",
        metadata={"volume": "0.01", "account_environment": "demo"},
    )
    target = DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("5"),
            aggregate_open_risk_pct=Decimal("9"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("25"),
            max_concurrent_positions=1,
        ),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    _plan, jobs = q.plan_and_enqueue(signal=signal, targets=[target], settings=settings)
    assert jobs
    worker_id = uuid4()
    claimed = q.claim_next(worker_id=worker_id, user_id=user, broker_account_id=account)
    assert claimed is not None
    q.mark_submitting(intent_id=claimed.intent_id, worker_id=worker_id)
    unknown = q.record_broker_execution(
        intent_id=claimed.intent_id,
        worker_id=worker_id,
        ok=False,
        retcode=None,
        order_ticket=None,
        deal_ticket=None,
        detail="order_send_null",
        broker_payload={"uncertain": True},
        outcome="unknown",
    )
    assert unknown.state is AccountExecutionState.UNKNOWN
    assert unknown.payload.get("retry_order_send_allowed") is False
    again = q.record_broker_execution(
        intent_id=claimed.intent_id,
        worker_id=worker_id,
        ok=True,
        retcode=10009,
        order_ticket=999,
        deal_ticket=1,
        detail="late_fill_ignored",
        outcome="filled",
    )
    assert again.state is AccountExecutionState.UNKNOWN


def test_ack_is_not_fill() -> None:
    q = DurableDispatchQueue()
    user, account = uuid4(), uuid4()
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="sig:12b-ack",
        metadata={"volume": "0.01", "account_environment": "demo"},
    )
    target = DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("5"),
            aggregate_open_risk_pct=Decimal("9"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("25"),
            max_concurrent_positions=1,
        ),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    _plan, jobs = q.plan_and_enqueue(signal=signal, targets=[target], settings=settings)
    assert jobs
    worker_id = uuid4()
    claimed = q.claim_next(worker_id=worker_id, user_id=user, broker_account_id=account)
    assert claimed is not None
    acked = q.acknowledge(intent_id=claimed.intent_id, worker_id=worker_id)
    assert acked.state is not AccountExecutionState.FILLED
    assert acked.payload.get("order_ticket") is None
