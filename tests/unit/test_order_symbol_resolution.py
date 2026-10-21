"""Manual order validation resolves Gold aliases to the exact broker symbol.

Regression: manual orders failed with "symbol mismatch". parse_order_intent
turns every Gold alias into "XAUUSD_I", while the live broker catalogue lists
gold as plain "XAUUSD" (verified on the gateway 2026-10-21). validate_order
built constraints from the resolved symbol but compared the unresolved one.
"""

from __future__ import annotations

import pytest

from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture
def service() -> MT5OrderValidationService:
    # Mock catalogue lists gold as plain "XAUUSD", like the live broker.
    adapter = MT5Adapter(client=MockMT5Client())
    adapter.initialize()
    adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
    return MT5OrderValidationService(adapter=adapter)


@pytest.mark.parametrize(
    "requested", ["XAUUSD", "xauusd", "XAUUSD_i", "XAUUSD_I", "GOLD", "gold"]
)
def test_gold_aliases_validate_against_broker_symbol(
    service: MT5OrderValidationService, requested: str
) -> None:
    intent = parse_order_intent(
        symbol=requested, side="buy", order_type="market", volume="0.01"
    )
    result = service.validate_order(intent)
    assert result.checks.get("symbol") is True, result.messages
    assert "symbol mismatch" not in " ".join(result.messages)
    assert result.symbol == "XAUUSD"


def test_symbol_compare_is_case_insensitive(service: MT5OrderValidationService) -> None:
    intent = parse_order_intent(
        symbol="XAUUSD", side="buy", order_type="market", volume="0.01"
    )
    constraints = service.constraints_for("XAUUSD")
    lowered = service._intent_with_symbol(intent, "xauusd")
    ok, msg = service.validate_symbol(lowered, constraints)
    assert ok is True, msg


def test_non_gold_symbol_is_rejected() -> None:
    with pytest.raises(ValidationError, match="DISABLED_AUTONOMOUS_SYMBOL"):
        parse_order_intent(
            symbol="EURUSD", side="buy", order_type="market", volume="0.01"
        )
