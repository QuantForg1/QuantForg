"""Unit tests — Institutional Execution Intelligence Layer."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.execution_optimizer import (
    clear_optimizer_defers,
    evaluate_execution_moment,
)
from app.domain.institutional_trading.ai_scalping.execution_quality_analytics import (
    classify_fill_quality,
    get_execution_quality_analytics_store,
)
from app.domain.institutional_trading.ai_scalping.institutional_position_monitor import (
    build_position_monitor,
)
from app.domain.institutional_trading.ai_scalping.operational_intelligence import (
    build_operational_intelligence,
)
from app.domain.institutional_trading.ai_scalping.smart_order_routing import (
    estimate_smart_routing,
)
from app.domain.institutional_trading.ai_scalping.trade_lifecycle_timeline import (
    LIFECYCLE_STAGES,
    get_trade_lifecycle_store,
)
from app.domain.institutional_trading.ai_scalping.execution_daily_reporting import (
    build_execution_daily_report,
)


@pytest.mark.unit
def test_execution_optimizer_never_forces_or_changes_direction() -> None:
    clear_optimizer_defers()
    decision = SimpleNamespace(
        action=SimpleNamespace(value="BUY"),
        symbol="XAUUSD",
        input_hash="hash-opt-1",
    )
    account = SimpleNamespace(atr=1.2, mid_price=2300.0)
    snapshot = SimpleNamespace(entry_closes=(2300.0, 2300.1, 2300.05))
    out = evaluate_execution_moment(
        symbol="XAUUSD",
        decision=decision,
        snapshot=snapshot,
        account=account,
        decision_key="hash-opt-1",
    )
    assert 0 <= out["execution_quality_score"] <= 100
    assert out["forced_trades"] is False
    assert out["direction_unchanged"] is True
    assert out["fabricated"] is False
    assert out["recommendation"] in {
        "PROCEED",
        "DEFER_TICK",
        "PROCEED_DEGRADED",
        "SKIP",
    }
    for key in (
        "spread_trend",
        "tick_momentum",
        "micro_volatility",
        "execution_latency",
        "broker_response_history",
        "slippage_history",
    ):
        assert key in out["components"]


@pytest.mark.unit
def test_optimizer_defer_respects_max_limit() -> None:
    clear_optimizer_defers()
    decision = SimpleNamespace(
        action=SimpleNamespace(value="BUY"),
        symbol="EURUSD",
        input_hash="hash-defer",
    )
    # Force low micro-vol via compression ATR
    account = SimpleNamespace(atr=0.0001, mid_price=1.1)
    snapshot = SimpleNamespace(entry_closes=(1.1, 1.12, 1.15))  # spike momentum
    last = None
    for _ in range(5):
        last = evaluate_execution_moment(
            symbol="EURUSD",
            decision=decision,
            snapshot=snapshot,
            account=account,
            decision_key="hash-defer",
        )
    assert last is not None
    assert last["recommendation"] in {"PROCEED_DEGRADED", "PROCEED", "DEFER_TICK"}
    assert last["defer_count"] <= last["max_defers"]


@pytest.mark.unit
def test_smart_routing_does_not_change_ai() -> None:
    sor = estimate_smart_routing(
        symbol="XAUUSD",
        side="BUY",
        spread=0.12,
        optimizer={"execution_quality_score": 70, "recommendation": "PROCEED"},
    )
    assert sor["ai_decision_unchanged"] is True
    assert sor["direction_unchanged"] is True
    assert sor["forced_trades"] is False
    assert 0.05 <= sor["fill_probability"] <= 0.98
    assert sor["execution_quality_score"] >= 0


@pytest.mark.unit
def test_execution_quality_analytics_record() -> None:
    store = get_execution_quality_analytics_store()
    row = store.record(
        symbol="XAUUSD",
        side="BUY",
        requested_price=2300.0,
        executed_price=2300.15,
        slippage=0.15,
        latency_ms=120.0,
        broker_execution_time_ms=120.0,
        fill_quality=classify_fill_quality(slippage=0.15, latency_ms=120),
        execution_score=72,
        outcome="success",
        ticket="123",
    )
    assert row["fabricated"] is False
    assert row["fill_quality"] in {"good", "fair", "poor", "unknown"}
    snap = store.snapshot()
    assert snap["samples"] >= 1
    assert snap["fabricated"] is False


@pytest.mark.unit
def test_lifecycle_timeline_stages() -> None:
    store = get_trade_lifecycle_store()
    lid = "lc-test-1"
    store.begin(lifecycle_id=lid, symbol="XAUUSD", direction="BUY")
    for stage in (
        "AI_APPROVED",
        "RISK_APPROVED",
        "PRE_APPROVED",
        "OMS_SUBMITTED",
        "BROKER_ACCEPTED",
        "FILLED",
        "MANAGED",
        "CLOSED",
        "ARCHIVED",
    ):
        store.mark(lid, stage, ok=True)
    snap = store.snapshot()
    assert snap["stages_schema"] == list(LIFECYCLE_STAGES)
    assert snap["fabricated"] is False
    assert any(r.get("id") == lid for r in snap["recent"])


@pytest.mark.unit
def test_position_monitor_real_positions_only() -> None:
    pos = SimpleNamespace(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=2300.0,
        current_sl=2295.0,
        current_tp=2310.0,
        remaining_volume=0.1,
        risk_distance=5.0,
        state=SimpleNamespace(value="TRAILING"),
    )
    mon = build_position_monitor([pos], mid_price=2305.0, atr=2.0, market_session="london")
    assert mon["open_positions"] == 1
    assert mon["fabricated"] is False
    assert mon["rows"][0]["remaining_rr"] is not None
    assert mon["rows"][0]["management_phase"] == "TRAILING"


@pytest.mark.unit
def test_operational_intelligence_warnings_only() -> None:
    ops = build_operational_intelligence()
    assert ops["stops_production"] is False
    assert ops["fabricated"] is False
    assert isinstance(ops["warnings"], list)


@pytest.mark.unit
def test_daily_report_never_fabricates() -> None:
    rep = build_execution_daily_report()
    assert rep["fabricated"] is False
    assert rep["trade_approval_rate"] is None or isinstance(
        rep["trade_approval_rate"], (int, float)
    )


@pytest.mark.unit
def test_noc_execution_intelligence_panels_shape() -> None:
    from app.application.services.noc_intelligence_panels import (
        build_intelligence_panels,
    )

    panels = build_intelligence_panels(runtime_scan={"opportunity_ranked": []})
    for key in (
        "execution_optimizer",
        "smart_order_routing",
        "execution_quality",
        "lifecycle_timeline",
        "position_monitor",
        "operational_intelligence",
        "daily_execution_report",
        "broker_performance",
    ):
        assert key in panels
    assert panels["flags"]["forced_trades"] is False
