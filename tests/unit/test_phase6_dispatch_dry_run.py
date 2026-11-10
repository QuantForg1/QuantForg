"""Phase 6 dispatch foundation — non-executing, flags off."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_dispatch_dry_run import (
    DispatchTarget,
    InMemoryDispatchLedger,
    plan_signal_dispatch,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)

pytestmark = [pytest.mark.unit]

_SETTINGS_OFF = SimpleNamespace(
    multi_account_dispatch_enabled=False,
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


def test_plan_suppresses_delivery_and_stays_dry_run() -> None:
    user = uuid4()
    account = uuid4()
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="signal:test-1",
    )
    plan = plan_signal_dispatch(
        signal=signal,
        targets=[
            DispatchTarget(
                user_id=user,
                broker_account_id=account,
                proposal=_proposal(),
                account=AccountReadiness(status="active", user_id=user),
                worker=WorkerReadiness(present=True, ready=True),
            )
        ],
        settings=_SETTINGS_OFF,
        require_readiness=True,
    )
    assert plan.dispatch_allowed is False
    assert plan.live_submit_allowed is False
    assert plan.to_dict()["delivery_suppressed_all"] is True
    item = plan.items[0]
    assert item.delivery_suppressed is True
    assert item.evaluation.dry_run is True
    assert item.intent.state is AccountExecutionState.ELIGIBLE
    assert item.intent.state is not AccountExecutionState.SUBMITTING


def test_idempotent_ledger_dedupes_same_key() -> None:
    ledger = InMemoryDispatchLedger()
    user = uuid4()
    account = uuid4()
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="signal:dup",
    )
    target = DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=_proposal(),
        account=AccountReadiness(status="active", user_id=user),
        worker=WorkerReadiness(present=True, ready=True),
    )
    first = plan_signal_dispatch(
        signal=signal,
        targets=[target],
        settings=_SETTINGS_OFF,
        require_readiness=True,
        ledger=ledger,
    )
    second = plan_signal_dispatch(
        signal=signal,
        targets=[target],
        settings=_SETTINGS_OFF,
        require_readiness=True,
        ledger=ledger,
    )
    assert first.items[0].idempotency_key == second.items[0].idempotency_key
    assert ledger.get(first.items[0].idempotency_key) is not None
    assert ledger.plan_count == 2


def test_foreign_actor_becomes_blocked_item_not_leak() -> None:
    owner = uuid4()
    stranger = uuid4()
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
    )
    plan = plan_signal_dispatch(
        signal=signal,
        targets=[
            DispatchTarget(
                user_id=owner,
                broker_account_id=uuid4(),
                actor_user_id=stranger,
                proposal=_proposal(),
                account=AccountReadiness(status="active", user_id=owner),
                worker=WorkerReadiness(present=True, ready=True),
            )
        ],
        settings=_SETTINGS_OFF,
        require_readiness=True,
    )
    assert plan.items[0].intent.state is AccountExecutionState.BLOCKED
    assert plan.items[0].delivery_suppressed is True


def test_source_has_no_order_send_or_oms_calls() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    text = (
        root / "app" / "application" / "services" / "multi_account_dispatch_dry_run.py"
    ).read_text(encoding="utf-8")
    # Docstrings may mention forbidden APIs; ensure no executable imports/calls.
    assert "gateway_client" not in text
    assert "import order" not in text
    assert "order_send(" not in text
    assert "LiveTrading" not in text
    assert "live_ok = False" in text
    assert "delivery_suppressed=True" in text
