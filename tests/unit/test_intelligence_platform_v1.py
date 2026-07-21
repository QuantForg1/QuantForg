"""Unit tests — QuantForg Intelligence Platform."""

from __future__ import annotations

from app.domain.intelligence_platform import (
    IntelligenceFeeds,
    IntelligencePlatformCenter,
)


def test_status_research_only_no_orders() -> None:
    center = IntelligencePlatformCenter()
    status = center.status()
    assert status["never_submits_orders"] is True
    assert status["never_affects_production"] is True
    assert status["fabricates_metrics"] is False
    caps = status["capabilities"]
    assert caps["broker_orders"] is False
    assert caps["replay_isolated"] is True


def test_unavailable_without_feeds() -> None:
    dash = IntelligencePlatformCenter().build_dashboard(IntelligenceFeeds())
    panels = dash["panels"]
    assert dash["never_submits_orders"] is True
    assert panels["replay_studio"]["status"] == "unavailable"
    assert panels["candle_playback"]["status"] == "unavailable"
    assert panels["trade_review_center"]["status"] == "unavailable"
    assert panels["weekly_reports"]["status"] == "unavailable"
    assert panels["research_workspace"]["data"]["href"] == "/research"


def test_no_fake_metrics_in_monthly() -> None:
    dash = IntelligencePlatformCenter().build_dashboard(
        IntelligenceFeeds(
            monthly_report={"period": "monthly", "trades": 3},
            execution_analytics={
                "status": "available",
                "sample_sizes": {"fills": 3},
            },
        )
    )
    monthly = dash["panels"]["monthly_performance_reports"]
    assert monthly["status"] == "available"
    assert "fabricated" not in str(monthly["data"]).lower()
    assert monthly["data"]["report"]["trades"] == 3


def test_decision_inspector_and_governance() -> None:
    hist = [
        {"audit_id": "a" * 12, "decision": "HOLD"},
        {"audit_id": "b" * 12, "decision": "REJECT"},
    ]
    dash = IntelligencePlatformCenter().build_dashboard(
        IntelligenceFeeds(
            decision_history=hist,
            execution_audits=[{"request_id": "r1", "stage": "OMS"}],
        )
    )
    assert dash["panels"]["decision_inspector"]["status"] == "available"
    assert dash["panels"]["decision_inspector"]["data"]["count"] == 2
    gov = dash["panels"]["ai_governance_audit"]
    assert gov["status"] == "available"
    assert gov["data"]["audit_count"] == 1


def test_candle_playback_never_invents() -> None:
    dash = IntelligencePlatformCenter().build_dashboard(
        IntelligenceFeeds(candles=[])
    )
    p = dash["panels"]["candle_playback"]
    assert p["status"] == "empty"
    assert p["data"]["invents_candles"] is False


def test_knowledge_base_auditable() -> None:
    center = IntelligencePlatformCenter()
    entry = center.add_knowledge(
        title="London open rule",
        body="Skip first 5 minutes on XAUUSD.",
        author="alice",
        tags=["session"],
    )
    assert entry["entry_id"].startswith("kb_")
    listed = center.list_knowledge()
    assert listed["status"] == "available"
    found = center.search_knowledge("london")
    assert found["status"] == "available"


def test_registry_and_promotion_compose() -> None:
    dash = IntelligencePlatformCenter().build_dashboard(
        IntelligenceFeeds(
            lab_registry={"strategies": [{"key": "mean-rev"}]},
            lab_promotion={"cases": [], "open_count": 0},
        )
    )
    assert dash["panels"]["strategy_registry_foundation"]["status"] == "available"
    assert (
        dash["panels"]["strategy_promotion_workflow"]["data"][
            "forwarded_to_live_execution"
        ]
        is False
    )


def test_ai_evaluation_modules() -> None:
    dash = IntelligencePlatformCenter().build_dashboard(
        IntelligenceFeeds(
            decision_status={"product": "DI"},
            ai_robot_status={"product": "Robot"},
            lab_status={"product": "Lab"},
        )
    )
    ai = dash["panels"]["ai_evaluation_dashboard"]
    assert ai["status"] == "available"
    assert ai["data"]["module_count"] == 3
    assert ai["data"]["never_submits_orders"] is True
