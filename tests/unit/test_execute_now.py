"""Execute Now payload mapping."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    ShadowCycleResult,
)
from app.domain.institutional_trading.decision_models import PriceZone
from decimal import Decimal


@pytest.mark.unit
def test_build_execute_now_payload_success() -> None:
    runtime = MagicMock(spec=InstitutionalIteRuntime)
    runtime._lock = __import__("threading").Lock()
    decision = SimpleNamespace(
        symbol="EURUSD",
        direction=SimpleNamespace(value="BUY"),
        approved_lots=Decimal("0.01"),
        entry_zone=PriceZone(low=Decimal("1.10"), high=Decimal("1.11"), mid=Decimal("1.105")),
        stop_zone=PriceZone(low=Decimal("1.09"), high=Decimal("1.095"), mid=Decimal("1.092")),
        target_zone=PriceZone(low=Decimal("1.12"), high=Decimal("1.13"), mid=Decimal("1.125")),
    )
    oms = SimpleNamespace(
        outcome="filled",
        order_ticket=12345678,
        deal_ticket=None,
        message="ok",
        fill_price=Decimal("1.105"),
    )
    runtime._last_decision = decision
    runtime._last_bridge_result = SimpleNamespace(oms_result=oms)
    cycle = ShadowCycleResult(
        ok=True,
        trace_id="t1",
        mode="LIVE",
        forwarded_to_oms=True,
        mt5_ticket=12345678,
        abort_reason="NONE",
        cycle_outcome="forwarded",
    )
    payload = InstitutionalIteRuntime.build_execute_now_payload(
        runtime, cycle, execution_ms=320.4
    )
    assert payload["success"] is True
    assert payload["ticket"] == "12345678"
    assert payload["direction"] == "BUY"
    assert payload["status"] == "SUCCESS"
    assert payload["execution_ms"] == 320


@pytest.mark.unit
def test_build_execute_now_payload_rejected_exact_reason() -> None:
    runtime = MagicMock(spec=InstitutionalIteRuntime)
    runtime._lock = __import__("threading").Lock()
    runtime._last_decision = SimpleNamespace(
        symbol="XAUUSD",
        direction=SimpleNamespace(value="BUY"),
        approved_lots=Decimal("0.01"),
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
    )
    runtime._last_bridge_result = SimpleNamespace(
        oms_result=SimpleNamespace(
            outcome="rejected",
            order_ticket=None,
            deal_ticket=None,
            message="Buy stop loss must be below entry price.",
        )
    )
    cycle = ShadowCycleResult(
        ok=True,
        trace_id="t2",
        mode="LIVE",
        forwarded_to_oms=True,
        oms_message="Buy stop loss must be below entry price.",
        abort_reason="OMS_REJECTED",
        cycle_outcome="aborted",
    )
    payload = InstitutionalIteRuntime.build_execute_now_payload(
        runtime, cycle, execution_ms=100
    )
    assert payload["success"] is False
    assert payload["status"] == "REJECTED"
    assert "Buy stop loss must be below entry price." in payload["reason"]
