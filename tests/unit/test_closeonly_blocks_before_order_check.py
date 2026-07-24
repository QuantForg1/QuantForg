"""Close-only broker mode must fail closed before MT5 order_check."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.mt5_order import OrderConstraints
from app.domain.execution_engine.journal import ExecutionJournalStore


class _FakeValidation(MT5OrderValidationService):
    def __init__(self) -> None:
        super().__init__(adapter=SimpleNamespace())  # type: ignore[arg-type]
        self.order_check_calls = 0

    def normalize_intent(self, intent):  # type: ignore[no-untyped-def]
        return intent, []

    def constraints_for(self, symbol: str) -> OrderConstraints:
        return OrderConstraints(
            symbol=symbol,
            min_volume=Decimal("0.01"),
            max_volume=Decimal("100"),
            volume_step=Decimal("0.01"),
            stops_level=0,
            freeze_level=0,
            trade_allowed=False,
            market_open=True,
            digits=3,
            point=Decimal("0.001"),
            contract_size=Decimal("100"),
            filling_mode=1,
            execution_mode="market",
            trade_mode="closeonly",
            visible=True,
            margin_calc_mode="",
        )

    def validate_volume(self, intent, constraints):  # type: ignore[no-untyped-def]
        return True, "ok"

    def validate_stops(self, intent, constraints, *, entry_price=None):  # type: ignore[no-untyped-def]
        return True, "ok"

    def build_order_request(self, intent):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            price=Decimal("4053"),
            to_dict=lambda: {"symbol": intent.symbol},
        )


@pytest.mark.unit
def test_closeonly_skips_order_check_with_exact_10044_reason() -> None:
    validation = _FakeValidation()

    class _Adapter:
        def order_check(self, request):  # type: ignore[no-untyped-def]
            validation.order_check_calls += 1
            raise AssertionError("order_check must not be called for closeonly")

    validation.adapter = _Adapter()  # type: ignore[assignment]
    engine = InstitutionalExecutionEngine(
        gateway=SimpleNamespace(),
        safety=SimpleNamespace(
            evaluate=lambda **_: SimpleNamespace(allowed=True, reasons=())
        ),
        order_validation=validation,
        intelligence=SimpleNamespace(observe=lambda **_: None),
        journal=ExecutionJournalStore(),
    )
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="4048",
        take_profit="4060",
        slippage=10,
        magic=1,
        comment="test",
    )
    result, _ = engine.run_submit(
        user_id=uuid4(),
        request_id="closeonly-test",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert result.outcome == "rejected"
    assert validation.order_check_calls == 0
    assert "retcode 10044" in (result.message or "")
    assert "closeonly" in (result.message or "").lower()
