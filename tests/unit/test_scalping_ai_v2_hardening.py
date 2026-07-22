"""Unit tests — Scalping AI V2.1 production hardening."""

from __future__ import annotations

from pathlib import Path

from app.domain.scalping_ai_v2 import ScalpingAiV2
from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.hardening import (
    classify_retry,
    next_backoff_with_jitter_ms,
    validate_market_data,
)
from app.domain.scalping_ai_v2.state_store import OperationalStateStore
from tests.unit.test_scalping_ai_v2 import _rich


def test_v21_version_and_modules() -> None:
    status = ScalpingAiV2().status()
    assert str(status["version"]).startswith("scalping-ai-v2.1")
    modules = status["modules"]
    assert "state_persistence" in modules
    assert "emergency_stop" in modules
    assert "soak_testing" in modules
    caps = status["capabilities"]
    assert caps["production_hardening_v21"] is True
    assert caps["never_second_auto_trading_loop"] is True
    assert caps["never_second_execution_engine"] is True


def test_emergency_stop_blocks_new_trades() -> None:
    system = ScalpingAiV2()
    system.arm_emergency_stop("unit_test")
    result = system.run_cycle(_rich())
    assert result["recommendation"] == "No Trade"
    assert any("Emergency" in r for r in result["reasons"])
    system.clear_emergency_stop()
    result2 = system.run_cycle(_rich(execution_identity="post_clear"))
    assert result2["recommendation"] == "Proceed"


def test_data_integrity_rejects_bad_ohlc() -> None:
    cfg = ScalpingAiV2Config()
    bad = _rich(
        market_data={
            "timestamp": "2026-07-22T12:00:00Z",
            "ohlc": {"o": 10, "h": 5, "l": 8, "c": 9},
        }
    )
    res = validate_market_data(bad, cfg)
    assert res.passed is False
    assert res.recommendation == "No Trade"


def test_mt5_drift_logged() -> None:
    system = ScalpingAiV2()
    result = system.run_cycle(
        _rich(
            execution_identity="mt5_drift_1",
            mt5_sync={
                "local_open_positions": 1,
                "mt5_open_positions": 2,
                "local_balance": 10000,
                "mt5_balance": 10000,
            },
        )
    )
    mt5 = result["modules"]["mt5_synchronization"]
    assert mt5["recommendation"] == "Reconcile"
    assert "mismatches" in mt5["details"]


def test_state_persistence_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "scalp_state.json"
    store = OperationalStateStore(path=path)
    system = ScalpingAiV2(state_store=store)
    system.run_cycle(_rich(execution_identity="persist_a"))
    system.arm_emergency_stop("persist")
    assert path.exists()

    store2 = OperationalStateStore(path=path)
    system2 = ScalpingAiV2(state_store=store2)
    assert system2.emergency.armed is True
    system2.clear_emergency_stop("test_clear")
    # Duplicate identity restored — must block after emergency clear
    blocked = system2.run_cycle(_rich(execution_identity="persist_a"))
    assert blocked["recommendation"] == "No Trade"
    assert any("Duplicate" in r for r in blocked["reasons"])


def test_safe_mode_pauses_new_trades() -> None:
    system = ScalpingAiV2()
    result = system.run_cycle(
        _rich(
            execution_identity="safe_1",
            health={
                "execution_loop": True,
                "broker_connection": False,
                "gateway": False,
                "database": True,
                "analytics": True,
                "risk_engine": True,
                "safety_engine": True,
                "decision_engine": True,
                "analytics_metrics": {"win_rate": 50},
            },
        )
    )
    assert result["recommendation"] == "No Trade"
    assert result["modules"]["safe_mode"]["details"]["safe_mode"] is True


def test_intelligent_retry_classification() -> None:
    assert classify_retry("duplicate_execution_identity")["retry"] is False
    assert classify_retry("broker_disconnect")["retry"] is True
    assert classify_retry("mystery")["retry"] is False
    cfg = ScalpingAiV2Config(max_retries=3, retry_backoff_ms=100)
    delay = next_backoff_with_jitter_ms(0, cfg, jitter_ratio=0.0)
    assert delay == 100
    assert next_backoff_with_jitter_ms(3, cfg) == -1


def test_soak_stress_passes() -> None:
    system = ScalpingAiV2(
        config=ScalpingAiV2Config(state_persist_enabled=False),
        state_store=OperationalStateStore(path=None),
    )
    report = system.run_soak(profile="stress")
    assert report["status"] == "passed"
    assert report["checks"]["duplicate_prevention"] is True
    assert report["checks"]["resource_cleanup"] is True
    assert report["never_order_send"] is True
    assert report["promise_profitability"] is False


def test_audit_contains_correlation() -> None:
    system = ScalpingAiV2()
    result = system.run_cycle(
        _rich(execution_identity="audit_1", correlation_id="corr_xyz")
    )
    assert result["correlation_id"] == "corr_xyz"
    audit = system.list_audit(limit=5)
    assert audit["status"] == "available"
    assert audit["items"][0]["correlation_id"] == "corr_xyz"
    assert "execution_identity" in audit["items"][0]


def test_restart_recovery_plan() -> None:
    system = ScalpingAiV2()
    result = system.run_cycle(
        _rich(execution_identity="restart_1", restart=True, health={
            "execution_loop": True,
            "broker_connection": True,
            "gateway": True,
            "database": True,
            "analytics": True,
            "risk_engine": True,
            "safety_engine": True,
            "decision_engine": True,
            "restart": True,
            "analytics_metrics": {"win_rate": 50},
        })
    )
    rr = result["modules"]["restart_recovery"]
    assert rr["recommendation"] == "Recover"
    assert rr["details"]["never_duplicate"] is True
    assert rr["details"]["never_creates_second_auto_trading_loop"] is True
