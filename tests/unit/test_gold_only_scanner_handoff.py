"""Gold-only must invoke the existing scanner and publish CURRENT_SCAN."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_multi_asset_scanner import (
    resolve_scan_universe,
    run_institutional_multi_asset_scan,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    build_last_pipeline_snapshot,
    opportunity_window_snapshot,
    reset_fast_decision_path,
)
from app.domain.trading.gold_only import is_gold_symbol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
_GOLD = "XAUUSD_I"
_FIRST = "Weak structure score 0 < 60"
_REJECTS = (
    _FIRST,
    "Momentum 0 < 55 — no confirmation",
    "No clear BUY/SELL edge (balanced scores → reject)",
)


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


def _runtime() -> InstitutionalIteRuntime:
    runtime = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(
            engine=SimpleNamespace(_positions={})
        ),
        mt5_adapter=MagicMock(),
    )
    return runtime


def _rejected_payload() -> dict:
    return {
        "as_of": "2026-08-19T12:55:00Z",
        "enabled": True,
        "best_symbol": None,
        "best_candidate": {
            "symbol": _GOLD,
            "eligible": False,
            "direction": "NONE",
        },
        "best_eligible_candidate": None,
        "eligible_count": 0,
        "eligible_symbols": [],
        "no_eligible_setup": True,
        "first_blocking_gate": "NO_ELIGIBLE_SETUP",
        "opportunity_ranked": [
            {
                "symbol": _GOLD,
                "opportunity_eligible": False,
                "eligible": False,
                "reject": True,
                "direction": "NONE",
                "reject_reason": "; ".join(_REJECTS),
                "reject_reasons": list(_REJECTS),
                "blocking_gate": _FIRST,
                "atr_pct": "0.122",
                "volatility_decision": {
                    "passed": True,
                    "atr_pct": "0.122",
                    "hard_min_pct": "0.08",
                    "band": "normal",
                },
            }
        ],
        "scanner_duration_ms": 12.3,
        "forced_trades": False,
    }


def _eligible_payload() -> dict:
    row = {
        "symbol": _GOLD,
        "opportunity_eligible": True,
        "eligible": True,
        "reject": False,
        "direction": "BUY",
        "opportunity_score": 88,
        "quality": 80,
        "confidence": 78,
        "atr_pct": "0.122",
        "volatility_decision": {
            "passed": True,
            "atr_pct": "0.122",
            "hard_min_pct": "0.08",
            "band": "normal",
        },
    }
    return {
        "as_of": "2026-08-19T12:55:00Z",
        "enabled": True,
        "best_symbol": _GOLD,
        "best_candidate": {
            "symbol": _GOLD,
            "eligible": True,
            "direction": "BUY",
        },
        "best_eligible_candidate": {"symbol": _GOLD, "eligible": True},
        "eligible_count": 1,
        "eligible_symbols": [_GOLD],
        "no_eligible_setup": False,
        "opportunity_ranked": [row],
        "scanner_duration_ms": 11.0,
        "forced_trades": False,
    }


async def _offload(fn, /, *args, **kwargs):  # noqa: ANN001
    return fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_gold_only_pick_invokes_existing_scanner(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime()
    called = {"n": 0}

    async def _scan(*_a, **_k):  # noqa: ANN002, ANN003
        called["n"] += 1
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_current_scan_decision,
            publish_current_scan_decision,
        )

        payload = _rejected_payload()
        decision = build_current_scan_decision(payload)
        payload["current_scan"] = decision
        publish_current_scan_decision(decision)
        return payload

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.run_institutional_multi_asset_scan",
        _scan,
    )
    monkeypatch.setattr(
        "app.application.services.closeonly_symbol_router.resolve_executable_symbol",
        lambda *_a, **_k: (_GOLD, []),
    )
    runtime._offload_blocking_io = _offload  # type: ignore[method-assign]
    reset_fast_decision_path()
    chosen = await runtime._pick_executable_symbol_async()
    assert called["n"] == 1
    assert chosen is None
    src = inspect.getsource(InstitutionalIteRuntime._pick_executable_symbol_async)
    assert "_multi_asset_preferred_symbol" in src
    assert "preferred = await self._multi_asset_preferred_symbol()" in src


@pytest.mark.asyncio
async def test_rejected_gold_publishes_named_current_scan(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime()

    async def _scan(*_a, **_k):  # noqa: ANN002, ANN003
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_current_scan_decision,
            publish_current_scan_decision,
        )

        payload = _rejected_payload()
        decision = build_current_scan_decision(payload)
        payload["current_scan"] = decision
        publish_current_scan_decision(decision)
        return payload

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.run_institutional_multi_asset_scan",
        _scan,
    )
    monkeypatch.setattr(
        "app.application.services.closeonly_symbol_router.resolve_executable_symbol",
        lambda *_a, **_k: (_GOLD, []),
    )
    runtime._offload_blocking_io = _offload  # type: ignore[method-assign]
    reset_fast_decision_path()
    chosen = await runtime._pick_executable_symbol_async()
    assert chosen is None
    snap = opportunity_window_snapshot()
    fd = runtime._fast_decision_snapshot()
    assert snap["setup_state"] != "MARKET_CONTEXT_NOT_READY"
    assert fd["decision_state"] != "MARKET_CONTEXT_NOT_READY"
    assert fd["next_action"] == CandidateAction.NO_EXECUTABLE_FOCUS.value
    assert fd["current_focus"] in {None, ""}
    assert str(fd["first_blocking_gate"]) == _FIRST
    assert str(fd["best_candidate"] or fd["current_best_candidate"]) == _GOLD
    assert int(fd["eligible_count"] or 0) == 0
    current = fd.get("current_scan") or {}
    assert current.get("label") == "CURRENT_SCAN"
    assert current.get("atr_pct") == "0.122"
    assert current.get("execution_ready") is False
    last = build_last_pipeline_snapshot(
        {"cycle_outcome": "no_trade", "abort_reason": "NO_TRADE"}
    )
    assert last is not None
    assert last["label"] == "LAST_COMPLETED_ITE_CYCLE"
    assert current.get("label") != last["label"]


@pytest.mark.asyncio
async def test_eligible_gold_becomes_best_eligible(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime()

    async def _scan(*_a, **_k):  # noqa: ANN002, ANN003
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_current_scan_decision,
            publish_current_scan_decision,
        )

        payload = _eligible_payload()
        decision = build_current_scan_decision(payload)
        payload["current_scan"] = decision
        publish_current_scan_decision(decision)
        return payload

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.run_institutional_multi_asset_scan",
        _scan,
    )
    monkeypatch.setattr(
        "app.application.services.closeonly_symbol_router.resolve_executable_symbol",
        lambda *_a, **_k: (_GOLD, []),
    )
    runtime._offload_blocking_io = _offload  # type: ignore[method-assign]
    reset_fast_decision_path()
    chosen = await runtime._pick_executable_symbol_async()
    assert chosen == _GOLD
    fd = runtime._fast_decision_snapshot()
    current = fd.get("current_scan") or {}
    assert is_gold_symbol(str(current.get("symbol") or chosen))
    assert int(current.get("eligible_count") or 0) == 1
    best_el = current.get("best_eligible") or {}
    assert str(best_el.get("symbol") or "") == _GOLD
    focus = str(fd.get("current_focus") or current.get("executable_focus") or "")
    assert not focus or is_gold_symbol(focus)
    if str(fd.get("next_action")) == CandidateAction.WAIT_SAME_FOCUS.value:
        assert is_gold_symbol(str(fd.get("current_focus") or ""))


@pytest.mark.asyncio
async def test_scanner_clamps_non_gold_out_of_universe(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    scored: list[str] = []

    async def _fake_score(_adapter, symbol: str, **_k):  # noqa: ANN001
        scored.append(str(symbol).upper())
        return {
            "symbol": symbol,
            "reject": True,
            "reject_reason": _FIRST,
            "reject_reasons": [_FIRST],
            "direction": "NONE",
            "ai_confidence": 39,
            "trade_quality": 52,
            "execution_health_ok": True,
            "atr_pct": "0.122",
        }

    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.score_symbol_for_scan",
        _fake_score,
    )
    monkeypatch.setattr(
        "app.application.services.institutional_multi_asset_scanner.resolve_scan_universe",
        lambda *_a, **_k: ("XAUUSD_I", "EURUSD_I", "GBPUSD"),
    )
    from dataclasses import replace

    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    cfg = replace(
        DEFAULT_AI_SCALPING_CONFIG,
        dynamic_universe_enabled=False,
        live_symbol_learning_enabled=False,
        parallel_scan_enabled=False,
    )
    reset_fast_decision_path()
    out = await run_institutional_multi_asset_scan(
        mt5_adapter=object(),
        config=cfg,
        open_positions=0,
    )
    assert scored == [_GOLD]
    assert "EURUSD_I" not in scored
    assert all(is_gold_symbol(s) for s in out.get("universe") or [])
    current = out.get("current_scan") or {}
    assert current.get("label") == "CURRENT_SCAN"
    assert current.get("first_blocking_gate") in {
        _FIRST,
        "OPPORTUNITY_SCORE_BELOW_THRESHOLD",
        "NO_ELIGIBLE_SETUP",
        "DIRECTION_NONE",
    }
    assert current.get("next_action") in {
        CandidateAction.NO_EXECUTABLE_FOCUS.value,
        CandidateAction.WAIT.value,
    }
    assert isinstance(out.get("scanner_duration_ms"), (int, float))


def test_scanner_universe_resolver_is_gold_only(gold_only: None) -> None:
    rows = (
        {"code": "EURUSD_i", "trade_mode": 4},
        {"code": "XAUUSD_i", "trade_mode": 4},
        {"code": "GBPUSD_i", "trade_mode": 4},
    )
    uni = resolve_scan_universe(broker_symbol_rows=rows)
    assert uni == ("XAUUSD_I",)
    assert "EURUSD" not in {s.upper() for s in uni}


def test_no_duplicate_scanner_and_no_forced_trade() -> None:
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert runtime_src.count("run_institutional_multi_asset_scan(") == 1
    tree = ast.parse(runtime_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "order_send":
                pytest.fail("ITE runtime must not call order_send directly")
    pick_src = inspect.getsource(InstitutionalIteRuntime._pick_executable_symbol_async)
    assert "copy_rates_from_pos" not in pick_src
    assert "latest_tick" not in pick_src
    scanner_src = (
        ROOT / "app/application/services/institutional_multi_asset_scanner.py"
    ).read_text(encoding="utf-8")
    assert "def run_institutional_multi_asset_scan" in scanner_src
    assert scanner_src.count("async def run_institutional_multi_asset_scan") == 1


def test_gold_only_no_longer_returns_before_scan() -> None:
    src = inspect.getsource(InstitutionalIteRuntime._pick_executable_symbol_async)
    assert "_multi_asset_preferred_symbol" in src
    gold_idx = src.find("if gold_only_enabled()")
    scan_idx = src.find("preferred = await self._multi_asset_preferred_symbol()")
    assert scan_idx != -1
    assert gold_idx == -1 or scan_idx < gold_idx


def test_safety_risk_oms_gateway_untouched() -> None:
    gates = (
        ROOT / "app/application/services/execution_safety.py"
    ).read_text(encoding="utf-8")
    gateway = (
        ROOT / "app/infrastructure/brokers/mt5/gateway_client.py"
    ).read_text(encoding="utf-8")
    assert "Never retry order_send" in gateway
    assert "order_send" in gateway
    assert "class ExecutionSafetyService" in gates
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "OrderSend" not in runtime_src
    assert "forces_trades" not in inspect.getsource(
        InstitutionalIteRuntime._pick_executable_symbol_async
    )
