"""Bridge journals exact NO_TRADE / ignored-action reasons."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    DecisionAction,
)
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionBridgeContext,
    ExecutionMode,
)


@pytest.mark.unit
def test_ignored_action_includes_decision_reasons() -> None:
    integ = InstitutionalExecutionIntegration.create(
        RecordingOmsPort(),
        config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW),
    )
    decision = SimpleNamespace(
        id=uuid4(),
        action=DecisionAction.NO_TRADE,
        direction=SimpleNamespace(value="FLAT"),
        confidence=20,
        quality=20,
        risk_score=0,
        approved_lots=None,
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
        estimated_rr=None,
        config_version="ite-v1",
        reasons=("Confidence too low", "Spread too high"),
        input_hash="diag_hash",
        symbol="XAUUSD",
        as_of=datetime(2026, 7, 22, 14, 0, tzinfo=UTC),
        eligibility=SimpleNamespace(eligible=False, rejection_reasons=("spread",)),
    )
    account = AccountRiskState(
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        free_margin=Decimal("5000"),
        mid_price=Decimal("2300"),
        atr=Decimal("1"),
    )
    snapshot = SimpleNamespace(
        symbol="XAUUSD",
        spread=Decimal("0.35"),
        session=SimpleNamespace(session="london", allowed=True),
        news=SimpleNamespace(blocked=False, reason=""),
    )
    ctx = ExecutionBridgeContext(
        snapshot=snapshot,  # type: ignore[arg-type]
        account=account,
        expected_input_hash="diag_hash",
        now=datetime(2026, 7, 22, 14, 0, tzinfo=UTC),
        user_id=uuid4(),
        execution_enabled=False,
        risk_allowed=True,
        connected=True,
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
    )
    result = integ.bridge.handle(decision, ctx)  # type: ignore[arg-type]
    assert result.abort_reason is BridgeAbortReason.IGNORED_ACTION
    assert "Confidence too low" in (result.journal_entry.comment or "")
    assert "Spread too high" in (result.journal_entry.comment or "")
    assert result.forwarded_to_oms is False
