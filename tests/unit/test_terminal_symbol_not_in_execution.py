"""Terminal view symbol must not participate in autonomous execution.

Does not change Safety, Risk, OMS, sizing, leverage, or whitelist.
Proves execution authority is decision/snapshot symbol, not UI state.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.domain.trading.gold_only import GOLD_SYMBOL, gold_only_enabled
from app.presentation.routers.institutional_ops import execute_now_auto_trading

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_PATHS = (
    ROOT / "app/application/services/institutional_ite_runtime.py",
    ROOT / "app/application/services/institutional_execution_engine.py",
    ROOT / "app/application/services/institutional_oms_adapter.py",
    ROOT / "app/domain/institutional_trading/execution/bridge.py",
    ROOT / "app/infrastructure/brokers/mt5/adapter.py",
    ROOT / "app/infrastructure/brokers/mt5/gateway_client.py",
    ROOT / "app/presentation/routers/institutional_ops.py",
)

FORBIDDEN_UI_TOKENS = (
    "selectedSymbol",
    "activeSymbol",
    "chartSymbol",
    "ticketSymbol",
    "TERMINAL_SYMBOL_KEY",
    "qf.workspace.symbol",
    "qf.terminal",
    "terminal_selected",
    "terminal.selected",
)


@pytest.fixture
def multi_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: False,
    )


@pytest.mark.unit
def test_gold_only_off_in_tests() -> None:
    assert gold_only_enabled() is False


@pytest.mark.unit
def test_execute_now_does_not_accept_a_terminal_symbol() -> None:
    sig = inspect.signature(InstitutionalIteRuntime.execute_now)
    assert list(sig.parameters) == ["self"]
    http_sig = inspect.signature(execute_now_auto_trading)
    assert "symbol" not in http_sig.parameters


@pytest.mark.unit
def test_pick_executable_symbol_has_no_terminal_parameter() -> None:
    sig = inspect.signature(InstitutionalIteRuntime._pick_executable_symbol_async)
    names = set(sig.parameters)
    assert names == {"self"}
    assert "terminal" not in names
    assert "selected" not in names


@pytest.mark.unit
def test_oms_intent_uses_decision_symbol_not_gold_home(
    multi_symbol: None,
) -> None:
    _ = multi_symbol
    intent = parse_order_intent(
        symbol="NZDUSD_I",
        side="buy",
        order_type="market",
        volume="0.01",
    )
    assert "NZDUSD" in str(intent.symbol).upper()
    assert GOLD_SYMBOL not in str(intent.symbol).upper()
    assert "XAUUSD" not in str(intent.symbol).upper()


@pytest.mark.unit
def test_oms_intent_ignores_a_terminal_view_symbol(
    multi_symbol: None,
) -> None:
    """Terminal=XAUUSD_i must not rewrite an NZDUSD_I OMS intent."""
    _ = multi_symbol
    terminal_view = "XAUUSD_i"
    execution = "NZDUSD_I"
    intent = parse_order_intent(
        symbol=execution,
        side="buy",
        order_type="market",
        volume="0.01",
        comment=f"terminal_view={terminal_view}",
    )
    assert "NZDUSD" in str(intent.symbol).upper()
    assert str(intent.symbol).upper() != terminal_view.upper()


@pytest.mark.unit
def test_execution_modules_do_not_read_terminal_ui_symbol() -> None:
    for path in EXECUTION_PATHS:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_UI_TOKENS:
            assert token not in text, f"{path.name} references UI symbol {token!r}"


@pytest.mark.unit
def test_bridge_builds_oms_intent_from_decision_symbol_source() -> None:
    """ExecutionBridge.parse_order_intent call site uses decision.symbol."""
    src = (
        ROOT / "app/domain/institutional_trading/execution/bridge.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "parse_order_intent":
            continue
        for kw in node.keywords:
            if kw.arg == "symbol":
                snippet = ast.unparse(kw.value)
                assert "decision.symbol" in snippet
                assert "terminal" not in snippet.lower()
                found = True
    assert found, "parse_order_intent(symbol=decision.symbol) not found"


@pytest.mark.unit
def test_gateway_order_send_uses_intent_symbol() -> None:
    src = (
        ROOT / "app/infrastructure/brokers/mt5/gateway_client.py"
    ).read_text(encoding="utf-8")
    assert "order_send" in src
    assert "qf.workspace.symbol" not in src
    engine = (
        ROOT / "app/application/services/institutional_execution_engine.py"
    ).read_text(encoding="utf-8")
    assert "intent.symbol" in engine
    assert "selectedSymbol" not in engine
