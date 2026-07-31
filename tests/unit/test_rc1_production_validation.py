"""RC1 Production Validation Pipeline — unit tests.

Asserts floors stay at 80/80 and broker is never submitted in paper/shadow.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.institutional_trading.rc1_production_validation.acceptance import (
    evaluate_acceptance_gates,
)
from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
    ValidationExecutionMode,
    clear_validation_runtime_override_for_tests,
    resolve_validation_runtime,
    set_validation_runtime_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.hooks import (
    handle_validation_execution,
)
from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
    reset_paper_engine_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.pipeline import (
    run_rc1_validation_pipeline,
)
from app.domain.institutional_trading.rc1_production_validation.replay import (
    build_synthetic_replay_dataset,
    run_replay_verification,
)
from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
    reset_shadow_journal_for_tests,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    reset_trade_recorder_for_tests,
)


def _reset() -> None:
    clear_validation_runtime_override_for_tests()
    reset_trade_recorder_for_tests()
    reset_paper_engine_for_tests()
    reset_shadow_journal_for_tests()


def test_floors_locked_at_eighty() -> None:
    assert QUALITY_FLOOR == 80
    assert CONFIDENCE_FLOOR == 80
    cfg = resolve_validation_runtime(enabled=True, execution_mode="paper")
    assert cfg.quality_floor == 80
    assert cfg.confidence_floor == 80


def test_execution_modes_parse() -> None:
    for mode in ("paper", "shadow", "live"):
        cfg = resolve_validation_runtime(enabled=True, execution_mode=mode)
        assert cfg.execution_mode is ValidationExecutionMode(mode)
    assert resolve_validation_runtime(
        enabled=True, execution_mode="paper"
    ).blocks_broker_submit
    assert resolve_validation_runtime(
        enabled=True, execution_mode="shadow"
    ).blocks_broker_submit
    assert not resolve_validation_runtime(
        enabled=True, execution_mode="live"
    ).blocks_broker_submit


def test_replay_histograms_and_coverage() -> None:
    _reset()
    events = build_synthetic_replay_dataset()
    result = run_replay_verification(events, execution_mode="shadow")
    assert result["eligible_trades"] >= 1
    assert result["rejected_trades"] >= 1
    assert result["quality_floor"] == 80
    assert result["confidence_floor"] == 80
    assert result["coverage"]["regimes_missing"] == []
    assert result["coverage"]["sessions_missing"] == []
    assert isinstance(result["quality_histogram"], dict)
    assert isinstance(result["confidence_histogram"], dict)
    assert result["expected_broker_submissions"]


def test_paper_engine_metrics_no_broker() -> None:
    engine = reset_paper_engine_for_tests(starting_equity=10_000)
    fill = engine.simulate_fill(
        symbol="XAUUSD",
        side="buy",
        entry=2350,
        stop_loss=2340,
        take_profit=2370,
        lots=0.01,
        partial_fill_pct=0.5,
    )
    assert fill["broker_submitted"] is False
    assert fill["partial"] is True
    pid = fill["position"]["position_id"]
    closed = engine.apply_bar(high=2375, low=2345, position_id=pid)
    assert closed
    perf = engine.performance()
    assert perf["broker_orders_submitted"] == 0
    assert perf["closed_positions"] == 1
    assert perf["profit_factor"] is not None or perf["expectancy"] is not None


def test_shadow_hook_never_submits() -> None:
    _reset()
    set_validation_runtime_for_tests(enabled=True, execution_mode="shadow")

    class _Dec:
        action = type("A", (), {"value": "BUY"})()
        symbol = "XAUUSD"
        quality = 88
        confidence = 90
        estimated_rr = "2.0"
        approved_lots = "0.01"
        id = "d1"
        stop_zone = type("Z", (), {"low": 2340, "high": 2345})()
        target_zone = type("Z", (), {"low": 2360, "high": 2370})()
        risk_score = 40
        snapshot = None
        entry_price = 2350

    class _Intent:
        def to_dict(self) -> dict:
            return {
                "symbol": "XAUUSD",
                "side": "buy",
                "volume": "0.01",
                "price": "2350",
                "stop_loss": "2340",
                "take_profit": "2370",
            }

    out = handle_validation_execution(
        decision=_Dec(), intent=_Intent(), latency_ms=11.0
    )
    assert out is not None
    assert out["broker_submitted"] is False
    assert out["execution_mode"] == "shadow"
    from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
        get_shadow_journal,
    )

    assert get_shadow_journal().stats()["broker_submissions"] == 0
    clear_validation_runtime_override_for_tests()


def test_paper_hook_simulates_fill() -> None:
    _reset()
    set_validation_runtime_for_tests(enabled=True, execution_mode="paper")

    class _Dec:
        action = type("A", (), {"value": "SELL"})()
        symbol = "XAUUSD"
        quality = 85
        confidence = 82
        estimated_rr = "1.8"
        approved_lots = "0.02"
        id = "d2"
        stop_zone = type("Z", (), {"low": 2360, "high": 2365})()
        target_zone = type("Z", (), {"low": 2330, "high": 2335})()
        risk_score = 35
        snapshot = None
        entry_price = 2355

    class _Intent:
        def to_dict(self) -> dict:
            return {
                "symbol": "XAUUSD",
                "side": "sell",
                "volume": "0.02",
                "price": "2355",
                "stop_loss": "2365",
                "take_profit": "2335",
            }

    out = handle_validation_execution(
        decision=_Dec(), intent=_Intent(), latency_ms=9.0
    )
    assert out is not None
    assert out["execution_mode"] == "paper"
    assert out["fill"]["simulated"] is True
    assert out["fill"]["broker_submitted"] is False
    clear_validation_runtime_override_for_tests()


def test_acceptance_and_full_pipeline(tmp_path: Path) -> None:
    _reset()
    set_validation_runtime_for_tests(enabled=True, execution_mode="paper")
    report = tmp_path / "RC1_VALIDATION_REPORT.md"
    result = run_rc1_validation_pipeline(
        write_report=True,
        report_path=report,
        use_synthetic_replay_if_empty=True,
        infrastructure={
            "gateway_status": "HEALTHY",
            "oms_status": "HEALTHY",
            "mt5_status": "CONNECTED",
            "ai_status": "OK",
            "crashes": 0,
        },
    )
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "RC1 Validation Report" in text
    assert "Final Recommendation" in text
    assert result["acceptance"]["quality_floor"] == 80
    assert result["acceptance"]["confidence_floor"] == 80
    assert result["recommendation"] in {
        "NOT READY",
        "READY FOR LIMITED LIVE PILOT",
        "READY FOR FULL PRODUCTION",
    }
    dash = result["dashboard"]
    assert "Eligible Trades" in dash
    assert "Latency" in dash
    assert dash["mode"]["never_modifies_strategy"] is True
    clear_validation_runtime_override_for_tests()


def test_acceptance_hard_fail_not_ready() -> None:
    acc = evaluate_acceptance_gates(
        infrastructure={"gateway_status": "FAIL", "crashes": 2},
        trade_stats={
            "accepted_quality_avg": 70,
            "accepted_confidence_avg": 70,
            "duplicate_penalties": 1,
        },
        paper={"broker_orders_submitted": 1},
        trading={"orders_valid": False},
        risk={"daily_loss_enforced": False, "emergency_stop_verified": False},
    )
    assert acc["recommendation"] == "NOT READY"
    assert acc["summary"]["failed"] >= 1
