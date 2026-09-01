"""Gold-only autonomous trading — universe restriction, not a risk bypass."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.services.closeonly_symbol_router import (
    build_opportunity_candidates,
    resolve_executable_symbol,
    select_full_mode_symbol,
)
from app.application.services.institutional_multi_asset_scanner import (
    resolve_scan_universe,
)
from app.domain.institutional_trading.auto_trading import AutoTradePolicy
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    apply_focus_hysteresis,
    build_current_scan_decision,
    build_last_pipeline_snapshot,
    classify_candidate_outcome,
    opportunity_window_snapshot,
    reset_fast_decision_path,
    set_focus,
)
from app.domain.trading.execution_universe import canonical_execution_desks
from app.domain.trading import gold_only as gold_policy
from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    GOLD_SYMBOL,
    autonomous_execution_symbols,
    gold_only_diagnostics,
    is_gold_symbol,
    require_xauusd,
)
from app.domain.trading.xauusd_specs import MAX_LEVERAGE
from core.config.environments import production_settings, testing_settings

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
WELTRADE_ROWS = (
    {"code": "AUDUSD_i", "trade_mode": 4},
    {"code": "EURUSD_i", "trade_mode": 4},
    {"code": "XAUUSD_i", "trade_mode": 4},
    {"code": "GBPUSD_i", "trade_mode": 4},
    {"code": "NZDUSD_i", "trade_mode": 4},
)
FX_DESKS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "US30", "NAS100", "BTCUSD")


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


class _Info:
    def __init__(self, trade_mode: str) -> None:
        self.trade_mode = trade_mode


class _Adapter:
    def __init__(self, modes: dict[str, str]) -> None:
        self.modes = modes

    def symbol_info(self, symbol: str) -> _Info:
        return _Info(self.modes.get(symbol.upper(), "full"))


def test_gold_only_mode_enabled(gold_only: None) -> None:
    assert gold_policy.gold_only_enabled() is True
    diag = gold_only_diagnostics(broker_symbol_rows=WELTRADE_ROWS)
    assert diag["gold_only_mode"] is True
    assert diag["trading_mode"] == "GOLD_ONLY"
    assert diag["other_pairs_autonomous"] == "DISABLED"
    assert diag["rotate_focus_allowed"] is False


def test_execution_universe_is_exactly_xauusd_i(gold_only: None) -> None:
    universe = autonomous_execution_symbols(broker_symbol_rows=WELTRADE_ROWS)
    assert universe == ("XAUUSD_I",)
    diag = gold_only_diagnostics(broker_symbol_rows=WELTRADE_ROWS)
    assert diag["execution_universe"] == ["XAUUSD_i"]
    assert diag["canonical_symbol"] == CANONICAL_GOLD_BROKER_DISPLAY
    assert diag["display_name"] == "XAUUSD (Gold)"
    assert diag["logical_symbol"] == GOLD_SYMBOL
    desks = canonical_execution_desks()
    assert desks == frozenset({GOLD_SYMBOL})
    for fx in FX_DESKS:
        assert fx not in desks


def test_gold_only_wins_over_multi_symbol_settings() -> None:
    settings = testing_settings(gold_only_mode=True, multi_symbol_enabled=True)
    assert settings.gold_only_mode is True


def test_production_remaps_gold_only_to_broker_discovered() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        gold_only_mode=True,
        multi_symbol_enabled=False,
        institutional_alpha_enabled=True,
        execution_universe_mode="GOLD_ONLY",
    )
    assert settings.gold_only_mode is False
    assert settings.multi_symbol_enabled is True
    assert str(settings.execution_universe_mode).upper() == "BROKER_DISCOVERED"
    assert bool(getattr(settings, "force_first_trade", False)) is False


def test_scanner_evaluates_xauusd_i_only(gold_only: None) -> None:
    uni = resolve_scan_universe(broker_symbol_rows=WELTRADE_ROWS)
    assert uni == ("XAUUSD_I",)
    assert "EURUSD_I" not in uni
    assert "GBPUSD" not in {s.upper() for s in uni}


def test_focused_pair_watch_only_gold(gold_only: None) -> None:
    reset_fast_decision_path()
    symbol, reason = apply_focus_hysteresis(
        current_focus="EURUSD_I",
        eligible_symbols=["EURUSD_I", "XAUUSD_I", "GBPUSD_I"],
        scores={"EURUSD_I": 90, "XAUUSD_I": 40, "GBPUSD_I": 80},
        proposed="EURUSD_I",
    )
    assert is_gold_symbol(symbol or "")
    assert symbol == "XAUUSD_I"
    assert "ROTATE" not in reason


def test_no_rotation_to_other_symbols(gold_only: None) -> None:
    out = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("minimum lot causes risk violation",),
        cycle_outcome="safety_blocked",
    )
    assert out["next_action"] == CandidateAction.WAIT_SAME_FOCUS.value
    assert out["candidate_action"] != CandidateAction.ROTATE_FOCUS.value
    assert out["fault_code"] == "MIN_LOT_CONSTRAINT"
    assert out["blocking_stage"] == "RISK"


def test_no_fallback_to_eurusd(gold_only: None) -> None:
    adapter = _Adapter({"XAUUSD": "closeonly", "XAUUSD_I": "closeonly", "EURUSD": "full"})
    selected, skipped = resolve_executable_symbol(
        adapter,
        preferred="XAUUSD",
        alpha_ranking=[{"symbol": "EURUSD", "opportunity_score": 90}],
        plane=SimpleNamespace(allowed_symbols=("EURUSD", "GBPUSD", "XAUUSD")),
    )
    assert selected is None or is_gold_symbol(selected)
    assert selected != "EURUSD"
    candidates = build_opportunity_candidates(
        preferred="EURUSD",
        plane=SimpleNamespace(allowed_symbols=("EURUSD", "NAS100")),
        alpha_ranking=[{"symbol": "GBPUSD"}],
    )
    assert candidates
    assert all(is_gold_symbol(s) for s in candidates)
    assert "EURUSD" not in candidates


def test_closeonly_gold_does_not_select_fx(gold_only: None) -> None:
    adapter = _Adapter(
        {
            "XAUUSD": "closeonly",
            "XAUUSD_I": "closeonly",
            "EURUSD": "full",
            "GBPUSD": "full",
        }
    )
    selected, skipped = select_full_mode_symbol(
        adapter, ["XAUUSD", "EURUSD", "GBPUSD"]
    )
    assert selected is None
    assert selected != "EURUSD"


def test_require_xauusd_preserves_broker_form(gold_only: None) -> None:
    from app.domain.trading.gold_only import (
        DISABLED_AUTONOMOUS_SYMBOL,
        DisabledAutonomousSymbolError,
    )

    assert require_xauusd("XAUUSD_I") == "XAUUSD_I"
    assert require_xauusd("XAUUSD_i") == "XAUUSD_I"
    with pytest.raises(DisabledAutonomousSymbolError, match="XAUUSD only") as ei:
        require_xauusd("EURUSD")
    assert ei.value.code == DISABLED_AUTONOMOUS_SYMBOL


@pytest.mark.parametrize(
    "symbol",
    ("EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD", "NAS100", "AUDUSD"),
)
def test_disabled_autonomous_symbols_rejected(
    gold_only: None, symbol: str
) -> None:
    from app.application.services.institutional_execution_engine import (
        parse_order_intent,
    )
    from app.domain.exceptions.base import ValidationError
    from app.domain.institutional_trading.operations.gold_execution_contract import (
        GoldExecutionFacts,
        evaluate_gold_execution_contract,
    )
    from app.domain.trading.gold_only import DISABLED_AUTONOMOUS_SYMBOL

    with pytest.raises(ValidationError) as ei:
        parse_order_intent(
            symbol=symbol,
            side="buy",
            order_type="market",
            volume="0.01",
        )
    assert ei.value.code == DISABLED_AUTONOMOUS_SYMBOL
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(symbol=symbol, gold_only=True)
    )
    assert out.may_submit_oms is False
    assert out.fault_code == DISABLED_AUTONOMOUS_SYMBOL
    assert is_gold_symbol(symbol) is False


def test_xauusd_i_accepted_for_autonomous_policy(gold_only: None) -> None:
    from app.domain.trading.gold_only import (
        DISABLED_AUTONOMOUS_SYMBOL,
        is_autonomous_execution_symbol,
    )

    assert is_autonomous_execution_symbol("XAUUSD_i") is True
    assert is_autonomous_execution_symbol("XAUUSD_I") is True
    assert require_xauusd("XAUUSD_i") == "XAUUSD_I"
    assert DISABLED_AUTONOMOUS_SYMBOL == "DISABLED_AUTONOMOUS_SYMBOL"
    from app.domain.trading.gold_only import resolve_trading_symbol

    assert resolve_trading_symbol("EURUSD") == "EURUSD"
    assert resolve_trading_symbol("XAUUSD") == "XAUUSD_I"


def test_current_scan_never_exposes_fx(gold_only: None) -> None:
    decision = build_current_scan_decision(
        {
            "as_of": "2026-08-19T00:00:00Z",
            "best_symbol": "EURUSD_I",
            "best_candidate": {
                "symbol": "EURUSD_I",
                "eligible": True,
                "blocking_gate": None,
                "direction": "BUY",
            },
            "eligible_count": 1,
            "eligible_symbols": ["EURUSD_I"],
            "opportunity_ranked": [
                {"symbol": "EURUSD_I", "opportunity_score": 88, "eligible": True}
            ],
        }
    )
    assert decision["label"] == "CURRENT_SCAN"
    symbol = str(decision.get("symbol") or "")
    assert not symbol or is_gold_symbol(symbol)
    assert decision.get("executable_focus") in {None, "XAUUSD", "XAUUSD_I"}
    assert "EURUSD" not in str(decision.get("symbol") or "")


def test_last_pipeline_separated_and_non_gold_hidden(gold_only: None) -> None:
    snap = build_last_pipeline_snapshot(
        {
            "cycle_outcome": "no_trade",
            "abort_reason": "NO_ELIGIBLE_SETUP",
            "market_context_diagnostics": {"symbol": "EURUSD_I"},
        }
    )
    assert snap is not None
    assert snap["label"] == "LAST_COMPLETED_ITE_CYCLE"
    assert snap["autonomous_valid"] is False
    assert snap["last_pipeline_symbol"] is None
    assert snap["last_pipeline_raw_symbol"] == "EURUSD_I"


def test_safety_and_risk_remain_authoritative(gold_only: None) -> None:
    kill = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("kill switch armed",),
    )
    assert kill["candidate_action"] == CandidateAction.FAIL_CLOSED.value
    leverage = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("account leverage 2001 exceeds max 2000",),
    )
    assert leverage["fault_code"] == "LEVERAGE_POLICY_EXCEEDED"
    assert leverage["fault_class"] == FaultClass.HARD_BLOCK.value
    assert leverage["next_action"] == CandidateAction.FAIL_CLOSED.value
    policy = AutoTradePolicy(enabled=True, run_state="running", trading_mode="scalping")
    assert all(is_gold_symbol(s) for s in policy.allowed_symbols)


def test_max_leverage_is_2000() -> None:
    src = (ROOT / "app/domain/trading/xauusd_specs.py").read_text(encoding="utf-8")
    assert 'MAX_LEVERAGE = Decimal("2000")' in src
    assert MAX_LEVERAGE == Decimal("2000")
    from app.domain.entities.execution_safety import ExecutionPolicy

    assert ExecutionPolicy().max_leverage == MAX_LEVERAGE


def test_no_order_send_bypass_or_retry() -> None:
    gateway = (
        ROOT / "app/infrastructure/brokers/mt5/gateway_client.py"
    ).read_text(encoding="utf-8")
    assert "Never retry order_send" in gateway
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(runtime_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "order_send":
                pytest.fail("ITE runtime must not call order_send directly")


def test_unknown_order_still_reconciles(gold_only: None) -> None:
    out = classify_candidate_outcome(abort_reason="ORDER_UNKNOWN")
    assert out["decision_state"] == DecisionState.ORDER_UNKNOWN.value
    assert out["next_action"] == CandidateAction.RECONCILE.value


def test_execute_now_not_required_for_autonomous() -> None:
    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )
    from app.presentation.routers.institutional_ops import execute_now_auto_trading

    src = inspect.getsource(InstitutionalIteRuntime._run_cycle)
    assert "self.execute_now" not in src
    assert "execute_now_auto_trading" not in src
    http_sig = inspect.signature(execute_now_auto_trading)
    assert "symbol" not in http_sig.parameters


def test_opportunity_window_observability_only(gold_only: None) -> None:
    reset_fast_decision_path()
    set_focus("EURUSD_I", reason="FOCUS_SELECTED")
    snap = opportunity_window_snapshot()
    assert snap["forces_trades"] is False
    focus = str(snap.get("current_focus") or "")
    assert not focus or is_gold_symbol(focus)


def test_no_forced_trade_flag() -> None:
    from app.domain.institutional_trading.operations.fast_decision_path import (
        opportunity_window_snapshot,
    )

    reset_fast_decision_path()
    snap = opportunity_window_snapshot()
    assert snap["forces_trades"] is False


def test_no_second_execution_authority() -> None:
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "OrderSend" not in runtime_src
    assert "MQL5" not in runtime_src


def test_browser_symbol_does_not_control_autonomous() -> None:
    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )

    sig = inspect.signature(InstitutionalIteRuntime.execute_now)
    assert "symbol" not in sig.parameters
    assert "selectedSymbol" not in sig.parameters


def test_gold_only_diagnostics_keys(gold_only: None) -> None:
    diag = gold_only_diagnostics(broker_symbol_rows=WELTRADE_ROWS)
    assert set(diag["execution_universe"]) == {"XAUUSD_i"}
    assert diag["gold_only_mode"] is True
    assert diag["desk_max_leverage"] == str(MAX_LEVERAGE)
