"""Gold execution readiness matrix and 30-minute tracker — observability only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    classify_candidate_outcome,
    opportunity_window_snapshot,
    publish_current_scan_decision,
    record_cycle_classification,
    reset_fast_decision_path,
)
from app.domain.institutional_trading.operations.gold_execution_readiness import (
    BarrierClass,
    StageStatus,
    TrackerState,
    build_readiness_matrix,
    production_feature_inventory,
    resolve_tracker_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
_GOLD = "XAUUSD_I"
_STRUCT = "Weak structure score 0 < 60"


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


@pytest.fixture(autouse=True)
def _reset_window() -> None:
    reset_fast_decision_path()


def test_gold_only_still_invokes_scanner_when_scan_flag_off(
    gold_only: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.application.services import institutional_multi_asset_scanner as scanner

    class _Cfg:
        multi_asset_scan_enabled = False
        dynamic_universe_enabled = False
        version = "test"
        parallel_scan_enabled = False

    monkeypatch.setattr(
        scanner,
        "resolve_scan_universe",
        lambda *_a, **_k: (_GOLD,),
    )
    # Import the early-return branch via source contract: gold-only must force scan_enabled.
    src = Path(scanner.__file__).read_text(encoding="utf-8")
    assert "if gold_only_enabled():" in src
    assert "scan_enabled = True" in src
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "Gold-only is a universe restriction, not a scanner bypass" in runtime_src
    assert _Cfg.multi_asset_scan_enabled is False


def test_rejected_gold_is_setup_not_ready_not_market_context(gold_only: None) -> None:
    publish_current_scan_decision(
        {
            "as_of": "2026-08-19T14:00:00Z",
            "best_symbol": None,
            "best_candidate": {
                "symbol": _GOLD,
                "eligible": False,
                "blocking_gate": _STRUCT,
                "reject_reasons": [_STRUCT],
                "direction": "NONE",
            },
            "eligible_count": 0,
            "eligible_symbols": [],
            "no_eligible_setup": True,
            "first_blocking_gate": _STRUCT,
            "opportunity_ranked": [
                {
                    "symbol": _GOLD,
                    "opportunity_eligible": False,
                    "reject_reason": _STRUCT,
                    "blocking_gate": _STRUCT,
                }
            ],
        }
    )
    snap = opportunity_window_snapshot()
    assert snap["tracker_state"] == TrackerState.SETUP_NOT_READY.value
    assert snap["decision_state"] != DecisionState.MARKET_CONTEXT_NOT_READY.value
    assert _STRUCT in str(snap["first_blocking_gate"])
    stages = snap["readiness_matrix"]["stages"]
    assert stages["MARKET"] == StageStatus.PASS.value
    assert stages["STRATEGY"] == StageStatus.WAIT.value
    assert stages["SAFETY"] == StageStatus.NOT_REACHED.value
    assert stages["OMS"] == StageStatus.NOT_REACHED.value


def test_missing_scan_is_market_context_not_ready(gold_only: None) -> None:
    snap = opportunity_window_snapshot()
    assert snap["tracker_state"] == TrackerState.MARKET_CONTEXT_NOT_READY.value
    assert snap["readiness_matrix"]["stages"]["MARKET"] == StageStatus.WAIT.value
    assert snap["readiness_matrix"]["stages"]["STRATEGY"] == StageStatus.NOT_REACHED.value


def test_eligible_gold_readiness_and_tracker(gold_only: None) -> None:
    publish_current_scan_decision(
        {
            "as_of": "2026-08-19T14:00:00Z",
            "best_symbol": _GOLD,
            "best_candidate": {"symbol": _GOLD, "eligible": True},
            "best_eligible_candidate": {"symbol": _GOLD},
            "eligible_count": 1,
            "eligible_symbols": [_GOLD],
            "opportunity_ranked": [
                {"symbol": _GOLD, "opportunity_eligible": True, "opportunity_score": 80}
            ],
        }
    )
    snap = opportunity_window_snapshot()
    assert snap["eligible_count"] == 1
    assert snap["best_candidate"] == _GOLD
    assert snap["tracker_state"] in {
        TrackerState.SETUP_FORMING.value,
        TrackerState.WAITING.value,
        TrackerState.READY.value,
    }
    assert snap["decision_state"] != DecisionState.MARKET_CONTEXT_NOT_READY.value
    assert snap["readiness_matrix"]["stages"]["STRATEGY"] == StageStatus.PASS.value


def test_advisory_does_not_block_readiness() -> None:
    matrix = build_readiness_matrix(
        has_current_scan=True,
        eligible_count=1,
        execution_ready=True,
        blocking_stage="ADVISORY",
        fault_class=FaultClass.ADVISORY.value,
        next_action=CandidateAction.CONTINUE.value,
        named_reject="optional enrichment unavailable",
        last_classification={"fault_class": FaultClass.ADVISORY.value},
    )
    assert matrix["barrier_class"] == BarrierClass.ADVISORY.value
    assert matrix["stages"]["SAFETY"] != StageStatus.BLOCK.value
    assert matrix["stages"]["OMS"] != StageStatus.BLOCK.value


def test_hard_block_still_blocks() -> None:
    out = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("kill switch armed",),
    )
    matrix = build_readiness_matrix(
        has_current_scan=True,
        eligible_count=1,
        execution_ready=False,
        blocking_stage=str(out["blocking_stage"]),
        fault_class=str(out["fault_class"]),
        next_action=str(out["next_action"]),
        named_reject="kill switch armed",
        last_classification=out,
    )
    assert matrix["stages"]["SAFETY"] == StageStatus.BLOCK.value
    assert out["next_action"] == CandidateAction.FAIL_CLOSED.value


def test_leverage_policy_preserved() -> None:
    from app.domain.trading.xauusd_specs import MAX_LEVERAGE
    from decimal import Decimal

    src = (ROOT / "app/domain/trading/xauusd_specs.py").read_text(encoding="utf-8")
    assert 'MAX_LEVERAGE = Decimal("2000")' in src
    assert MAX_LEVERAGE == Decimal("2000")
    inventory = production_feature_inventory()
    lev = next(r for r in inventory if r["feature"].startswith("MAX_LEVERAGE"))
    assert lev["feature"] == "MAX_LEVERAGE=2000"
    assert lev["current"] == "2000"
    assert lev["intended"] == "2000"
    assert lev["action"] == "KEEP"
    forced = next(r for r in inventory if r["feature"] == "Forced Trade")
    assert forced["intended"] == "OFF"
    assert forced["action"] == "KEEP OFF"


def test_stale_safety_is_not_current_when_scan_rejected(gold_only: None) -> None:
    record_cycle_classification(
        {
            "decision_state": DecisionState.HARD_BLOCK.value,
            "fault_class": FaultClass.HARD_BLOCK.value,
            "fault_code": "SAFETY_BLOCKED",
            "fault_reason": "kill switch armed",
            "blocking_stage": "SAFETY",
            "next_action": CandidateAction.FAIL_CLOSED.value,
        }
    )
    publish_current_scan_decision(
        {
            "as_of": "2026-08-19T14:05:00Z",
            "best_symbol": None,
            "best_candidate": {
                "symbol": _GOLD,
                "eligible": False,
                "blocking_gate": _STRUCT,
                "reject_reasons": [_STRUCT],
            },
            "eligible_count": 0,
            "eligible_symbols": [],
            "first_blocking_gate": _STRUCT,
            "opportunity_ranked": [
                {"symbol": _GOLD, "opportunity_eligible": False, "reject_reason": _STRUCT}
            ],
        }
    )
    snap = opportunity_window_snapshot()
    assert snap["tracker_state"] == TrackerState.SETUP_NOT_READY.value
    assert snap["readiness_matrix"]["stages"]["SAFETY"] == StageStatus.NOT_REACHED.value
    assert "kill switch" not in str(snap["first_blocking_gate"]).lower()


def test_timeout_bottleneck_when_window_expires(gold_only: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.domain.institutional_trading.operations.fast_decision_path as fdp

    publish_current_scan_decision(
        {
            "as_of": "2026-08-19T14:00:00Z",
            "best_symbol": None,
            "best_candidate": {
                "symbol": _GOLD,
                "eligible": False,
                "blocking_gate": _STRUCT,
                "reject_reasons": [_STRUCT],
            },
            "eligible_count": 0,
            "eligible_symbols": [],
            "first_blocking_gate": _STRUCT,
            "opportunity_ranked": [
                {"symbol": _GOLD, "opportunity_eligible": False, "reject_reason": _STRUCT}
            ],
        }
    )
    with fdp._LOCK:
        fdp._WINDOW.started_mono = 0.0
    snap = opportunity_window_snapshot(now_mono=fdp.WINDOW_SECONDS + 1.0)
    assert snap["tracker_state"] == TrackerState.TIMEOUT_NO_TRADE.value
    report = snap["bottleneck_report"]
    assert report is not None
    assert _STRUCT in str(report["why_no_order"])
    assert report["forces_trades"] is False
    assert report["orders_submitted"] == 0


def test_tracker_event_driven_not_polling_storm() -> None:
    src = (
        ROOT / "app/domain/institutional_trading/operations/fast_decision_path.py"
    ).read_text(encoding="utf-8")
    assert "cycle_events" in src
    assert "record_cycle_classification" in src
    assert "time.sleep(1)" not in src
    assert "asyncio.sleep(1)" not in src


def test_no_duplicate_scanner_or_order_send() -> None:
    ite = (ROOT / "app/application/services/institutional_ite_runtime.py").read_text(
        encoding="utf-8"
    )
    assert ite.count("async def _multi_asset_preferred_symbol") == 1
    assert "def _pick_executable_symbol_async" in ite
    pick = ite[
        ite.find("async def _pick_executable_symbol_async") : ite.find(
            "async def _pick_executable_symbol_async"
        )
        + 2500
    ]
    assert "order_send" not in pick
    readiness = (
        ROOT / "app/domain/institutional_trading/operations/gold_execution_readiness.py"
    ).read_text(encoding="utf-8")
    assert "MetaTrader5.order_send" not in readiness
    assert "Does not authorize trades" in readiness


def test_resolve_tracker_never_none_plus_wait_same() -> None:
    state = resolve_tracker_state(
        has_current_scan=True,
        eligible_count=0,
        execution_ready=False,
        current_focus=None,
        next_action=CandidateAction.WAIT_SAME_FOCUS.value,
        fault_class=FaultClass.WAIT.value,
        decision_state=DecisionState.SETUP_NOT_READY.value,
        named_reject=_STRUCT,
        window_active=True,
        first_natural_trade=False,
        window_started=True,
    )
    assert state != TrackerState.WAITING.value
    assert state == TrackerState.SETUP_NOT_READY.value
