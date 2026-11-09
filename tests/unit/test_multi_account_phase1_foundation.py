"""Phase 1 multi-account foundation — flags, effective risk, dispatch models.

Does not touch LIVE ITE / OMS / PME. Does not enable LIVE fan-out.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.multi_account.effective_risk import (
    ADMIN_ONLY_RISK_KEYS,
    USER_EDITABLE_RISK_KEYS,
    RiskSettingProposal,
    default_user_risk_proposal,
    resolve_effective_risk,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)
from core.config.settings import Settings

pytestmark = [pytest.mark.unit]


def test_feature_flags_default_off() -> None:
    settings = Settings(_env_file=None)
    assert settings.multi_account_dispatch_enabled is False
    assert settings.multi_account_live_submit_enabled is False
    assert multi_account_dispatch_allowed(settings) is False
    assert multi_account_live_submit_allowed(settings) is False


def test_live_submit_requires_dispatch() -> None:
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=False,
        multi_account_live_submit_enabled=True,
    )
    assert multi_account_live_submit_allowed(settings) is False

    settings.multi_account_dispatch_enabled = True
    assert multi_account_live_submit_allowed(settings) is True


def test_user_editable_keys_are_exactly_five() -> None:
    expected = {
        "planned_risk_pct",
        "aggregate_open_risk_pct",
        "max_lot",
        "daily_loss_pct",
        "max_concurrent_positions",
    }
    assert expected == USER_EDITABLE_RISK_KEYS
    assert ADMIN_ONLY_RISK_KEYS.isdisjoint(USER_EDITABLE_RISK_KEYS)


def test_default_proposal_copies_hard_ceilings() -> None:
    proposal = default_user_risk_proposal()
    effective = resolve_effective_risk(proposal)
    assert effective.ok is True
    assert effective.planned_risk_pct == Decimal("20.0")
    assert effective.max_lot == Decimal("0.01")
    assert effective.max_concurrent_positions == 1
    assert effective.daily_loss_pct == Decimal("48.0")
    assert effective.aggregate_open_risk_pct == Decimal("30.0")


def test_user_cannot_exceed_hard_ceiling() -> None:
    proposal = RiskSettingProposal(
        planned_risk_pct=Decimal("25"),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )
    effective = resolve_effective_risk(proposal)
    assert effective.ok is False
    assert effective.block_reason == "invalid_or_missing_risk_profile"
    assert any("planned_risk_pct" in f for f in effective.rejected_fields)


def test_admin_ceiling_stricter_than_user_request() -> None:
    proposal = RiskSettingProposal(
        planned_risk_pct=Decimal("15"),
        aggregate_open_risk_pct=Decimal("20"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("20"),
        max_concurrent_positions=1,
    )
    effective = resolve_effective_risk(
        proposal,
        admin_maxima={"planned_risk_pct": "10", "daily_loss_pct": "15"},
    )
    assert effective.ok is False
    assert any(
        "planned_risk_pct:exceeds_allowed_ceiling" in f
        for f in effective.rejected_fields
    )


def test_missing_profile_fails_closed() -> None:
    effective = resolve_effective_risk(RiskSettingProposal())
    assert effective.ok is False
    assert effective.block_reason == "invalid_or_missing_risk_profile"
    assert len(effective.rejected_fields) >= 5


def test_aggregate_below_planned_fails_closed() -> None:
    proposal = RiskSettingProposal(
        planned_risk_pct=Decimal("20"),
        aggregate_open_risk_pct=Decimal("10"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )
    effective = resolve_effective_risk(proposal)
    assert effective.ok is False
    assert effective.block_reason == "aggregate_open_risk_below_planned_risk"


def test_account_isolation_on_dispatch_models() -> None:
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="buy",
        quality=77,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key="sig-demo-1",
    )
    user_a = uuid4()
    user_b = uuid4()
    acct_a = uuid4()
    acct_b = uuid4()

    exec_a = AccountExecutionIntent.for_account(
        signal=signal, user_id=user_a, broker_account_id=acct_a
    )
    exec_b = AccountExecutionIntent.for_account(
        signal=signal, user_id=user_b, broker_account_id=acct_b
    )

    assert exec_a.signal_id == exec_b.signal_id == signal.signal_id
    assert exec_a.execution_id != exec_b.execution_id
    assert exec_a.idempotency_key != exec_b.idempotency_key
    assert exec_a.idempotency_key.endswith(str(acct_a))
    assert exec_b.idempotency_key.endswith(str(acct_b))

    blocked = exec_a.transition(
        AccountExecutionState.BLOCKED, block_reason="daily_loss_halt"
    )
    still_open = exec_b.transition(AccountExecutionState.ELIGIBLE)
    assert blocked.state is AccountExecutionState.BLOCKED
    assert still_open.state is AccountExecutionState.ELIGIBLE
    assert blocked.is_terminal is True
    assert still_open.is_terminal is False


def test_terminal_state_cannot_resubmit() -> None:
    signal = CentralSignalIntent.create(symbol="XAUUSD", side="SELL", quality=80)
    intent = AccountExecutionIntent.for_account(
        signal=signal, user_id=uuid4(), broker_account_id=uuid4()
    )
    rejected = intent.transition(AccountExecutionState.REJECTED, block_reason="broker")
    with pytest.raises(ValueError, match="terminal"):
        rejected.transition(AccountExecutionState.SUBMITTING)
