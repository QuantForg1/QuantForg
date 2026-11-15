"""Phase 6 — Institutional Intelligence unit coverage."""

from __future__ import annotations

from app.application.services import institutional_intelligence as ii
from app.domain.institutional_intelligence import (
    MODEL_VERSION,
    MODULE_ROUTES,
    RECOMMENDATION_STATUSES,
    isolation_payload,
)
from app.domain.institutional_intelligence.overview import (
    build_execution_overview,
    build_hub_summary,
    build_market_overview,
    build_portfolio_overview,
    build_risk_overview,
    build_strategy_overview,
)
from app.domain.institutional_intelligence.recommendations import RecommendationStore


def test_isolation_blocks_live_and_rebalance() -> None:
    flags = isolation_payload()
    assert flags["never_order_send"] is True
    assert flags["never_auto_rebalance"] is True
    assert flags["never_increases_risk_limits"] is True
    assert flags["never_guarantees_forecasts"] is True
    assert flags["approved_is_not_live"] is True
    assert flags["model_version"] == MODEL_VERSION


def test_health_service() -> None:
    h = ii.health()
    assert h["ok"] is True
    assert h["order_send"] is False
    assert h["auto_rebalance"] is False


def test_hub_lists_modules() -> None:
    hub = build_hub_summary()
    assert len(hub["modules"]) == len(MODULE_ROUTES)
    paths = {m["path"] for m in hub["modules"]}
    assert "/intelligence-center" in paths
    assert "/predictive-market-intelligence" in paths


def test_market_forecast_not_guaranteed() -> None:
    out = build_market_overview(
        symbol="XAUUSD",
        regime_label="ranging",
        regime_confidence=70,
    )
    assert out["ok"] is True
    assert out["forecast"] is not None
    assert out["forecast"]["guarantees_outcome"] is False
    assert "limitations" in out["forecast"]
    assert out["never_guarantees_forecasts"] is True


def test_market_missing_liquidity_honest() -> None:
    out = build_market_overview(
        symbol="XAUUSD", regime_label="ranging", regime_confidence=70
    )
    missing = out["data_quality"]["missing_fields"]
    assert "liquidity" in missing


def test_strategy_does_not_fabricate_metrics() -> None:
    empty = build_strategy_overview(strategies=[])
    assert empty["empty"] is True
    labeled = build_strategy_overview(
        strategies=[
            {
                "strategy_id": "s1",
                "result_class": "backtest",
                "metrics": {"win_rate": 0.55, "invented": "x"},
            }
        ]
    )
    assert labeled["strategies"][0]["metrics"] == {"win_rate": 0.55}
    assert labeled["strategies"][0]["result_class"] == "backtest"


def test_execution_empty_not_fabricated() -> None:
    out = build_execution_overview(attempts=[])
    assert out["empty"] is True
    assert out["metrics"]["success_rate"] is None
    assert out["metrics"]["fabricated"] is False
    filled = build_execution_overview(
        attempts=[
            {"outcome": "filled", "latency_ms": 20},
            {"outcome": "rejected", "latency_ms": 40},
        ]
    )
    assert filled["metrics"]["attempt_count"] == 2
    assert filled["metrics"]["success_rate"] == 0.5


def test_portfolio_never_invents_equity() -> None:
    out = build_portfolio_overview(qpm={}, household={})
    assert out["household"]["equity"] is None
    assert out["household"]["balance"] is None
    assert "equity_or_balance" in out["data_quality"]["missing_fields"]
    assert out["rules"]["never_auto_rebalance"] is True


def test_risk_hard_limits_priority() -> None:
    out = build_risk_overview(ati_alerts=[])
    assert out["enforcement"]["hard_limits_priority"] is True
    assert out["enforcement"]["ai_cannot_override_hard_constraints"] is True


def test_recommendation_lifecycle_and_approved_not_live() -> None:
    store = RecommendationStore()
    row = store.create(
        recommendation="Tighten risk",
        reasoning_summary="Drawdown rising",
        supporting_evidence=["dd"],
        risks_and_limitations=["Advisory"],
        expected_benefits=["Lower exposure"],
    )
    assert row["status"] == "Proposed"
    assert row["approved_is_not_live"] is True

    mid = store.set_status(row["id"], status="Under Review")
    assert mid and mid.get("ok") is True
    bad = store.set_status(row["id"], status="Applied")
    assert bad and bad.get("ok") is False

    ok = store.set_status(row["id"], status="Approved")
    assert ok and ok.get("ok") is True
    assert ok.get("never_authorizes_live_execution") is True
    assert ok["status"] == "Approved"

    assert len(RECOMMENDATION_STATUSES) == 6
