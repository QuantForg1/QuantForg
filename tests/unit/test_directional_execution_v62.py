"""Directional execution — BUY/SELL/NO_TRADE without BUY bias."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.decision_models import (
    ConfluenceResult,
    DecisionAction,
    TradeDirection,
)
from app.domain.institutional_trading.executable_direction import (
    resolve_executable_direction,
)
from app.domain.institutional_trading.execution.bridge import ExecutionBridge
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    ExecutionBridgeContext,
    ExecutionMode,
)
from app.domain.institutional_trading.force_first_trade import resolve_force_direction
from app.domain.market_structure.enums import TrendDirection


def _conf(direction: TradeDirection, *, passed: bool = True) -> ConfluenceResult:
    return ConfluenceResult(
        confidence=85 if passed else 40,
        direction=direction,
        reasons=("test",),
        rejected_rules=(),
        input_hash="dir_hash",
        band="tradable" if passed else "reject",
        passed=passed,
        factors={},
    )


@pytest.mark.unit
def test_ai_sell_is_authoritative_when_gates_pass() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.NONE, passed=False),
        ai_direction="SELL",
        ai_reject=False,
        scalping=True,
    )
    assert exe.direction is TradeDirection.SELL
    assert exe.source == "ai"


@pytest.mark.unit
def test_ai_buy_is_authoritative_when_gates_pass() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.NONE, passed=False),
        ai_direction="BUY",
        ai_reject=False,
        scalping=True,
    )
    assert exe.direction is TradeDirection.BUY
    assert exe.source == "ai"


@pytest.mark.unit
def test_ai_sell_vs_confluence_buy_is_no_trade() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.BUY),
        ai_direction="SELL",
        ai_reject=False,
        scalping=True,
    )
    assert exe.direction is TradeDirection.NONE
    assert "disagrees" in exe.reason.lower() or "NO_TRADE" in exe.reason


@pytest.mark.unit
def test_ai_buy_vs_confluence_sell_is_no_trade() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.SELL),
        ai_direction="BUY",
        ai_reject=False,
        scalping=True,
    )
    assert exe.direction is TradeDirection.NONE


@pytest.mark.unit
def test_weak_ai_reject_is_no_trade() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.BUY),
        ai_direction="BUY",
        ai_reject=True,
        scalping=True,
    )
    assert exe.direction is TradeDirection.NONE


@pytest.mark.unit
def test_never_defaults_none_to_buy() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.NONE, passed=False),
        ai_direction=None,
        ai_reject=None,
        scalping=True,
    )
    assert exe.direction is TradeDirection.NONE
    assert exe.source == "none"


@pytest.mark.unit
def test_swing_uses_confluence_sell() -> None:
    exe = resolve_executable_direction(
        confluence=_conf(TradeDirection.SELL),
        ai_direction=None,
        scalping=False,
    )
    assert exe.direction is TradeDirection.SELL
    assert exe.source == "confluence"


@pytest.mark.unit
def test_bridge_sell_action_builds_sell_intent() -> None:
    oms = MagicMock()
    bridge = ExecutionBridge(oms=oms, config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW))
    decision = MagicMock()
    decision.action = DecisionAction.SELL
    decision.stop_zone = MagicMock(low=Decimal("2310"), high=Decimal("2315"))
    decision.target_zone = MagicMock(low=Decimal("2290"), high=Decimal("2295"))
    decision.approved_lots = Decimal("0.01")
    decision.symbol = "XAUUSD"
    decision.input_hash = "abcdefghijklmnop"
    decision.reasons = ()
    intent = bridge._build_intent(decision, MagicMock())
    assert str(intent.side.value if hasattr(intent.side, "value") else intent.side).lower() in {
        "sell",
        "OrderSide.SELL".lower(),
    }
    # parse_order_intent returns OrderIntent with side enum
    side_raw = getattr(intent.side, "value", intent.side)
    assert str(side_raw).lower() == "sell"


@pytest.mark.unit
def test_bridge_buy_action_builds_buy_intent() -> None:
    oms = MagicMock()
    bridge = ExecutionBridge(oms=oms, config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW))
    decision = MagicMock()
    decision.action = DecisionAction.BUY
    decision.stop_zone = MagicMock(low=Decimal("2290"), high=Decimal("2295"))
    decision.target_zone = MagicMock(low=Decimal("2310"), high=Decimal("2315"))
    decision.approved_lots = Decimal("0.01")
    decision.symbol = "XAUUSD"
    decision.input_hash = "abcdefghijklmnop"
    decision.reasons = ()
    intent = bridge._build_intent(decision, MagicMock())
    side_raw = getattr(intent.side, "value", intent.side)
    assert str(side_raw).lower() == "buy"


@pytest.mark.unit
def test_force_auto_flat_bias_does_not_invent_buy() -> None:
    snap = MagicMock()
    snap.trend.macro_bias = TrendDirection.RANGE
    conf = _conf(TradeDirection.NONE, passed=False)
    assert (
        resolve_force_direction(configured="AUTO", snapshot=snap, confluence=conf)
        is None
    )
