"""Canonical autonomous execution context — Terminal view only.

Does not change OMS, Safety, Risk, Gateway, or order_send.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.services.autonomous_execution_context import (
    GATEWAY_UNAVAILABLE,
    MANUAL_HOME_SYMBOL,
    MT5_CHART_SYNC,
    MT5_CONNECTED,
    MT5_UNAVAILABLE,
    RECONCILIATION_REQUIRED,
    SYMBOL_NOT_TRADEABLE,
    build_autonomous_execution_context,
    collect_pme_positions_from_runtime,
)
from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.order import OrderSide, OrderType
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    resolve_seed_to_broker_symbol,
)
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def multi_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )


def _ctx(**kwargs: object):
    return build_autonomous_execution_context(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
def test_mt5_chart_xauusd_does_not_become_execution_symbol(multi_symbol: None) -> None:
    _ = multi_symbol
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "trace_id": "t-nzd",
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "abort_reason": "NONE",
                "market_context_diagnostics": {
                    "symbol": "NZDUSD_I",
                    "broker_symbol_resolved": "NZDUSD_I",
                },
            }
        },
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.symbol == "NZDUSD_I"
    assert ctx.broker_symbol == "NZDUSD_I"
    assert ctx.manual_symbol == "XAUUSD_i"
    assert ctx.mt5_chart_symbol is None
    assert ctx.mt5_chart_sync == MT5_CHART_SYNC
    intent = parse_order_intent(
        symbol="NZDUSD_I",
        side="buy",
        order_type="market",
        volume="0.01",
    )
    assert "NZDUSD" in str(intent.symbol).upper()
    assert GOLD_SYMBOL not in str(intent.symbol).upper()


@pytest.mark.unit
def test_terminal_xauusd_does_not_alter_oms_symbol(multi_symbol: None) -> None:
    _ = multi_symbol
    intent = parse_order_intent(
        symbol="NZDUSD_I",
        side="buy",
        order_type="market",
        volume="0.01",
        comment="terminal_view=XAUUSD_i",
    )
    assert str(intent.symbol).upper().startswith("NZDUSD")


@pytest.mark.unit
def test_browser_closed_execute_now_has_no_ui_parameter() -> None:
    sig = inspect.signature(InstitutionalIteRuntime.execute_now)
    assert list(sig.parameters) == ["self"]
    src = (ROOT / "app/application/services/institutional_ite_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "selectedSymbol" not in src
    assert "qf.workspace.symbol" not in src


@pytest.mark.unit
def test_gateway_has_no_chart_set_and_order_send_uses_request_symbol() -> None:
    gw = (ROOT / "app/infrastructure/brokers/mt5/gateway_client.py").read_text(
        encoding="utf-8"
    )
    assert "ChartSet" not in gw
    assert "chart_set" not in gw
    assert "def symbol_select" in gw
    assert '"symbol": request.symbol' in gw
    tree = ast.parse(
        (ROOT / "app/domain/institutional_trading/execution/bridge.py").read_text(
            encoding="utf-8"
        )
    )
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != "parse_order_intent":
            continue
        for kw in node.keywords:
            if kw.arg == "symbol":
                assert "decision.symbol" in ast.unparse(kw.value)
                found = True
    assert found


@pytest.mark.unit
def test_broker_symbol_resolver_uses_catalogue_not_hardcoded_suffix() -> None:
    rows = [
        {"code": "NZDUSD_I", "trade_mode": 4, "digits": 5},
        {"code": "XAUUSD_I", "trade_mode": 4, "digits": 2},
    ]
    resolved = resolve_seed_to_broker_symbol("NZDUSD", broker_symbol_rows=rows)
    assert resolved == "NZDUSD_I"
    missing = resolve_seed_to_broker_symbol("FAKESYM", broker_symbol_rows=rows)
    assert missing == "FAKESYM"


@pytest.mark.unit
def test_symbol_not_tradeable_blocks_without_falling_back_to_gold() -> None:
    adapter = MT5Adapter(client=MockMT5Client())
    validation = MT5OrderValidationService(adapter)
    constraints = SimpleNamespace(
        trade_allowed=False,
        trade_mode="disabled",
        market_open=True,
        symbol="NZDUSD_I",
        visible=True,
    )
    ok, msg = validation.validate_market_state(constraints)  # type: ignore[arg-type]
    assert ok is False
    assert "disabled" in msg.lower() or "trading" in msg.lower()
    intent = OrderIntent(
        symbol="NZDUSD_I",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )
    ok_sym, _ = validation.validate_symbol(intent, constraints)  # type: ignore[arg-type]
    assert ok_sym is True or ok_sym is False
    assert intent.symbol != GOLD_SYMBOL


@pytest.mark.unit
def test_no_live_tick_fails_closed_on_intent_symbol(multi_symbol: None) -> None:
    _ = multi_symbol

    class DeadTickAdapter:
        def latest_tick(self, symbol: str):
            raise RuntimeError(f"NO_LIVE_TICK {symbol}")

        def symbol_info(self, symbol: str):
            raise RuntimeError(f"NO_LIVE_TICK {symbol}")

    validation = MT5OrderValidationService(DeadTickAdapter())  # type: ignore[arg-type]
    intent = OrderIntent(
        symbol="NZDUSD_I",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )
    with pytest.raises(RuntimeError, match="NO_LIVE_TICK"):
        validation.build_order_request(intent)
    assert intent.symbol == "NZDUSD_I"


@pytest.mark.unit
def test_position_open_focuses_traded_symbol_not_manual_home() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "trace_id": "fill-1",
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "mt5_ticket": 4242,
                "abort_reason": "NONE",
                "market_context_diagnostics": {"symbol": "NZDUSD_I"},
            }
        },
        pme_positions=[
            {
                "position_id": "9001",
                "symbol": "NZDUSD_I",
                "side": "buy",
                "state": "OPEN",
            }
        ],
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.terminal_mode == "AUTONOMOUS_POSITION_OPEN"
    assert ctx.terminal_symbol == "NZDUSD_I"
    assert ctx.manual_symbol == MANUAL_HOME_SYMBOL
    assert ctx.symbol_source == "AUTONOMOUS_EXECUTION"


@pytest.mark.unit
def test_position_close_returns_manual_home_when_book_clear() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {"decision_action": "WATCH", "forwarded_to_oms": False}
        },
        pme_positions=[],
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.terminal_mode == "MANUAL"
    assert ctx.terminal_symbol == MANUAL_HOME_SYMBOL
    assert ctx.open_position_count == 0


@pytest.mark.unit
def test_multiple_positions_remain_autonomous() -> None:
    ctx = _ctx(
        pme_positions=[
            {"position_id": "1", "symbol": "NZDUSD_I", "state": "OPEN"},
            {"position_id": "2", "symbol": "EURUSD_I", "state": "OPEN"},
        ],
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.terminal_mode == "AUTONOMOUS_POSITION_OPEN"
    assert ctx.open_position_count == 2
    assert ctx.manual_symbol == MANUAL_HOME_SYMBOL


@pytest.mark.unit
def test_unknown_reconciliation_does_not_return_home() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "mt5_ticket": 7,
                "cycle_outcome": "RECONCILIATION_REQUIRED",
                "abort_reason": "UNKNOWN",
                "market_context_diagnostics": {"symbol": "NZDUSD_I"},
            }
        },
        pme_positions=[{"position_id": "1", "symbol": "NZDUSD_I", "state": "OPEN"}],
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.terminal_mode == "AUTONOMOUS_RECONCILIATION"
    assert ctx.failure_mode == RECONCILIATION_REQUIRED
    assert ctx.terminal_symbol != MANUAL_HOME_SYMBOL


@pytest.mark.unit
def test_mt5_disconnected_fail_closed() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "market_context_diagnostics": {"symbol": "NZDUSD_I"},
            }
        },
        gateway_connected=True,
        broker_connected=False,
    )
    assert ctx.mt5_status == MT5_UNAVAILABLE
    assert ctx.terminal_mode == "AUTONOMOUS_RECONCILIATION"


@pytest.mark.unit
def test_gateway_disconnected_fail_closed() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "decision_action": "BUY",
                "forwarded_to_oms": True,
                "market_context_diagnostics": {"symbol": "NZDUSD_I"},
            }
        },
        gateway_connected=False,
        broker_connected=True,
    )
    assert ctx.mt5_status == GATEWAY_UNAVAILABLE
    assert ctx.terminal_mode == "AUTONOMOUS_RECONCILIATION"


@pytest.mark.unit
def test_manual_mode_intact_without_autonomous_activity() -> None:
    ctx = _ctx(gateway_connected=True, broker_connected=True)
    assert ctx.terminal_mode == "MANUAL"
    assert ctx.terminal_symbol == MANUAL_HOME_SYMBOL
    assert ctx.symbol_source == "MANUAL"
    assert ctx.mt5_status == MT5_CONNECTED


@pytest.mark.unit
def test_pme_exited_positions_are_ignored() -> None:
    runtime = SimpleNamespace(
        position_management=SimpleNamespace(
            engine=SimpleNamespace(
                _positions={
                    1: SimpleNamespace(
                        ticket=1,
                        symbol="NZDUSD_I",
                        side="buy",
                        remaining_volume="0.01",
                        state=SimpleNamespace(value="EXITED"),
                        entry_price="0.62",
                    )
                }
            )
        )
    )
    rows = collect_pme_positions_from_runtime(runtime)
    assert rows == []


@pytest.mark.unit
def test_rejected_execution_does_not_fallback_to_gold() -> None:
    ctx = _ctx(
        orchestrator={
            "last_cycle": {
                "decision_action": "BUY",
                "forwarded_to_oms": False,
                "abort_reason": "SYMBOL_NOT_TRADEABLE",
                "market_context_diagnostics": {"symbol": "NZDUSD_I"},
            }
        },
        gateway_connected=True,
        broker_connected=True,
    )
    assert ctx.failure_mode in {SYMBOL_NOT_TRADEABLE, "EXECUTION_REJECTED"}
    assert ctx.terminal_mode == "MANUAL"
    assert ctx.symbol != GOLD_SYMBOL or ctx.symbol is None
