"""Phase 5 — preference-aware multi-account eligibility (LIVE off)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_eligibility_service import (
    evaluate_account_eligibility,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)

pytestmark = [pytest.mark.unit]


def _intent_for(user_id, account_id) -> AccountExecutionIntent:
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
    )
    return AccountExecutionIntent.for_account(
        signal=signal,
        user_id=user_id,
        broker_account_id=account_id,
    )


def test_flags_off_marks_dry_run_and_never_claims_live_submit() -> None:
    user = uuid4()
    account = uuid4()
    intent = _intent_for(user, account)
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=False,
        multi_account_live_submit_enabled=False,
    )
    updated, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=intent,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        ),
        settings=settings,
    )
    assert evaluation.dry_run is True
    assert evaluation.dispatch_allowed is False
    assert evaluation.live_submit_allowed is False
    assert updated.state is AccountExecutionState.ELIGIBLE
    assert updated.planned_volume == Decimal("0.01")
    assert updated.metadata["eligibility"]["dry_run"] is True


def test_stricter_user_prefs_remain_eligible_under_ceilings() -> None:
    user = uuid4()
    intent = _intent_for(user, uuid4())
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=False,
        multi_account_live_submit_enabled=False,
    )
    _updated, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=intent,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("20"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("20"),
            max_concurrent_positions=1,
        ),
        settings=settings,
    )
    assert evaluation.state is AccountExecutionState.ELIGIBLE
    assert evaluation.effective["planned_risk_pct"] == "10"
    assert evaluation.block_reason is None


def test_over_ceiling_max_lot_blocks() -> None:
    user = uuid4()
    intent = _intent_for(user, uuid4())
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=False,
    )
    updated, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=intent,
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("0.05"),
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        ),
        settings=settings,
    )
    assert updated.state is AccountExecutionState.BLOCKED
    assert evaluation.state is AccountExecutionState.BLOCKED
    assert evaluation.block_reason
    rejected = evaluation.effective.get("rejected_fields") or []
    assert any("max_lot" in str(item) for item in rejected)


def test_foreign_actor_denied() -> None:
    owner = uuid4()
    stranger = uuid4()
    intent = _intent_for(owner, uuid4())
    with pytest.raises(AuthorizationError):
        evaluate_account_eligibility(
            actor_user_id=stranger,
            intent=intent,
            proposal=RiskSettingProposal(
                planned_risk_pct=Decimal("10"),
                aggregate_open_risk_pct=Decimal("30"),
                max_lot=Decimal("0.01"),
                daily_loss_pct=Decimal("48"),
                max_concurrent_positions=1,
            ),
            settings=SimpleNamespace(
                multi_account_dispatch_enabled=False,
                multi_account_live_submit_enabled=False,
            ),
        )


def test_preference_loader_source_propagates() -> None:
    user = uuid4()
    intent = _intent_for(user, uuid4())

    def loader(_uid):
        return {
            "source": "user_edit",
            "persisted": True,
            "preferences": {
                "planned_risk_pct": "10.0000",
                "aggregate_open_risk_pct": "30.0000",
                "max_lot": "0.01",
                "daily_loss_pct": "48.0",
                "max_concurrent_positions": 1,
            },
        }

    _updated, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=intent,
        load_preferences=loader,
        settings=SimpleNamespace(
            multi_account_dispatch_enabled=False,
            multi_account_live_submit_enabled=False,
        ),
    )
    assert evaluation.source == "user_edit"
    assert evaluation.state is AccountExecutionState.ELIGIBLE
