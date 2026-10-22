"""Manual terminal orders obey the owner live limits end to end.

Owner screenshot 2026-10-21 ~19:39 UTC: BUY 0.01 XAUUSD (Gold) from /terminal,
ask ~4133.05, SL 4110, TP 4180 -> planned SL loss $23.05 (45% of $50.84).
The mock quotes gold at ask 2320.80, so the same 23.05 distance is used there.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

MOCK_ASK = Decimal("2320.80")
SL_DIST = Decimal("23.05")


def _engine() -> tuple[InstitutionalExecutionEngine, MockMT5Client]:
    client = MockMT5Client()
    client.initialize()
    client.login(MT5LoginRequest(login=1, password="p", server="S"))
    client._positions = []
    adapter = MT5Adapter(client=client, execution_enabled=True)
    validation = MT5OrderValidationService(adapter=adapter)
    engine = InstitutionalExecutionEngine(
        gateway=ExecutionGateway(adapter=adapter, order_validation=validation),
        safety=ExecutionSafetyService(adapter=adapter, order_validation=validation),
        order_validation=validation,
        intelligence=ExecutionIntelligenceService(),
        journal=ExecutionJournalStore(),
    )
    return engine, client


@pytest.mark.parametrize("symbol", ["XAUUSD", "XAUUSD_i", "GOLD"])
def test_manual_submit_with_23_dollar_sl_is_rejected(symbol: str) -> None:
    engine, client = _engine()
    intent = parse_order_intent(
        symbol=symbol,
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss=str(MOCK_ASK - SL_DIST),
        take_profit=str(MOCK_ASK + Decimal("46.95")),
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id=f"manual-{symbol}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == "rejected"
    assert pipeline.execution_result is None or not getattr(
        pipeline.execution_result, "order_ticket", None
    )
    assert client._positions == []


@pytest.mark.parametrize("symbol", ["XAUUSD", "XAUUSD_i", "GOLD"])
def test_manual_submit_in_band_passes_symbol_validation(symbol: str) -> None:
    # $1.80 SL, TP 3.20 away -> RR after spread >= 1.5; no "symbol mismatch".
    engine, _client = _engine()
    intent = parse_order_intent(
        symbol=symbol,
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.00",
    )
    pipeline, decision = engine.run_submit(
        user_id=uuid4(),
        request_id=f"manual-ok-{symbol}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert decision.decision.value == "allow", pipeline
    assert "symbol mismatch" not in str(pipeline).lower()


def _risk_engine() -> RiskEngine:
    return RiskEngine(
        config=RiskEngineConfig(
            min_lot=Decimal("0.01"),
            lot_step=Decimal("0.01"),
            max_lot=Decimal("0.01"),
            contract_size=Decimal("100"),
        )
    )


def _account() -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=Decimal("50.84"),
        equity=Decimal("50.84"),
        margin=Decimal("0"),
        free_margin=Decimal("50.84"),
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=2000,
    )


def _max_risk_rule(stop: str) -> tuple[RiskDecision, dict[str, object]]:
    assessment = _risk_engine().evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id=f"ticket-{stop}",
            symbol="XAUUSD",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal(stop),
            sizing_method=PositionSizingMethod.FIXED_LOT,
            entry_price=Decimal("4133.05"),
            contract_size=Decimal("100"),
        ),
        account=_account(),
        positions=[],
    )
    rule = next(r for r in assessment.rules if r.get("id") == "max_risk")
    return assessment.decision, rule


def test_ticket_risk_check_uses_owner_band_for_23_dollar_sl() -> None:
    decision, rule = _max_risk_rule("23.05")
    assert decision is RiskDecision.REJECT
    assert rule["status"] == "fail"
    assert str(rule["current"]).startswith("$23.05")
    assert "owner" in str(rule["threshold"])


def test_ticket_risk_check_passes_inside_owner_band() -> None:
    _decision, rule = _max_risk_rule("1.80")
    assert rule["status"] == "pass"
    assert str(rule["current"]).startswith("$1.80")


def test_ticket_risk_check_has_no_minimum_floor() -> None:
    # Old $1.50 floor removed: a $1.50 planned loss passes the per-trade rule.
    _decision, rule = _max_risk_rule("1.50")
    assert rule["status"] == "pass"
