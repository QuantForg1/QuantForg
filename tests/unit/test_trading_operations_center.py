"""Unit tests — Institutional Trading Operations Center (advisory)."""

from __future__ import annotations

import pytest

from app.domain.trading_operations_center.alerts import detect_operational_alerts
from app.domain.trading_operations_center.brief import build_daily_brief
from app.domain.trading_operations_center.checklist import build_operations_checklist
from app.domain.trading_operations_center.dashboard import (
    build_trading_operations_center,
)
from app.domain.trading_operations_center.reports import (
    build_end_of_day_report,
    build_monthly_review,
    build_weekly_review,
)


def _trades() -> list[dict]:
    return [
        {
            "net_pnl": 20,
            "session": "london",
            "r_multiple": 2.0,
            "opened_at": "2026-07-20T08:00:00+00:00",
            "closed_at": "2026-07-20T09:00:00+00:00",
        },
        {
            "net_pnl": -8,
            "session": "new_york",
            "r_multiple": -0.8,
            "opened_at": "2026-07-20T15:00:00+00:00",
            "closed_at": "2026-07-20T15:30:00+00:00",
        },
    ]


def _prev_trades() -> list[dict]:
    return [
        {
            "net_pnl": 5,
            "session": "london",
            "r_multiple": 1.0,
            "opened_at": "2026-07-13T08:00:00+00:00",
            "closed_at": "2026-07-13T09:00:00+00:00",
        },
        {
            "net_pnl": -10,
            "session": "new_york",
            "r_multiple": -1.0,
            "opened_at": "2026-07-13T15:00:00+00:00",
            "closed_at": "2026-07-13T15:40:00+00:00",
        },
    ]


@pytest.mark.unit
class TestTradingOperationsCenter:
    def test_checklist_shows_why_and_resolution(self) -> None:
        checklist = build_operations_checklist(
            {
                "gateway_connected": True,
                "broker_connected": False,
                "mt5_logged_in": True,
                "market_open": True,
                "xauusd_ready": True,
                "risk_ready": True,
                "safety_ready": True,
                "execution_enabled": False,
                "ops_mode": "SHADOW",
                "evidence_healthy": False,
            }
        )
        assert checklist["all_passed"] is False
        fails = {f["key"]: f for f in checklist["failures"]}
        assert "broker_connected" in fails
        assert fails["broker_connected"]["why"]
        assert fails["broker_connected"]["how_to_resolve"]
        assert "ops_live" in fails
        assert "execution_enabled" in fails

    def test_checklist_unknown_never_assumed_healthy(self) -> None:
        checklist = build_operations_checklist({})
        assert checklist["passed_count"] == 0
        assert all(i["status"] == "unknown" for i in checklist["items"])

    def test_daily_brief_calendar_unavailable(self) -> None:
        brief = build_daily_brief(calendar_available=False)
        assert brief["high_impact_news"]["status"] == "unavailable"
        assert brief["high_impact_news"]["items"] == []

    def test_alerts_never_suggest_strategy(self) -> None:
        alerts = detect_operational_alerts(
            ops_facts={"gateway_connected": False},
            evidence_summary={"live_records": 0, "replay_opportunities": 0},
            confidence={"overall_confidence": "insufficient"},
            decisions=[
                {"decision": "NO_TRADE", "reason": "spread too wide"},
                {"decision": "NO_TRADE", "reason": "spread too wide"},
            ],
        )
        assert alerts["never_suggests_strategy_changes"] is True
        codes = {a["code"] for a in alerts["alerts"]}
        assert "missing_evidence" in codes
        assert "gateway_instability" in codes
        assert "repeated_no_trade" in codes
        assert all(a["suggests_strategy_change"] is False for a in alerts["alerts"])

    def test_weekly_improvements_regressions(self) -> None:
        from app.domain.performance_intelligence.dashboard import (
            compute_performance_dashboard,
            normalize_trade_rows,
        )

        curr = compute_performance_dashboard(normalize_trade_rows(_trades()))
        prev = compute_performance_dashboard(normalize_trade_rows(_prev_trades()))
        weekly = build_weekly_review(current_week=curr, previous_week=prev)
        assert weekly["never_suggests_strategy_changes"] is True
        assert isinstance(weekly["improvements"], list)
        assert isinstance(weekly["regressions"], list)
        assert isinstance(weekly["unknowns"], list)

    def test_eod_and_monthly(self) -> None:
        from app.domain.performance_intelligence.dashboard import (
            build_performance_intelligence,
        )

        pack = build_performance_intelligence(trades=_trades(), period="daily")
        eod = build_end_of_day_report(
            performance=pack["performance"],
            sessions=pack["sessions"],
            no_trade=pack["no_trade"],
            evidence_summary={"replay_opportunities": 3, "live_records": 1},
            confidence={
                "lane_samples": {
                    "replay_opportunities": {"coverage": 0.006},
                }
            },
        )
        assert eod["trades"] == 2
        monthly = build_monthly_review(
            performance=pack["performance"],
            evidence_summary={"gates_passed": False},
            confidence={"overall_confidence": "insufficient"},
        )
        assert monthly["open_research_topics"]
        assert monthly["never_suggests_strategy_changes"] is True

    def test_full_pack_executive_dashboard(self) -> None:
        pack = build_trading_operations_center(
            ops_facts={
                "gateway_connected": True,
                "broker_connected": True,
                "mt5_logged_in": True,
                "market_open": True,
                "xauusd_ready": True,
                "risk_ready": True,
                "safety_ready": True,
                "execution_enabled": True,
                "ops_mode": "LIVE",
                "market_regime": "trend",
                "volatility_expectation": "elevated",
                "trading_date": "2026-07-22",
            },
            trades=_trades(),
            previous_week_trades=_prev_trades(),
            decisions=[
                {"decision": "NO_TRADE", "reason": "spread too wide"},
                {"decision": "NO_TRADE", "reason": "spread too wide"},
            ],
            high_impact_news=[{"title": "FOMC", "impact": "high"}],
            calendar_available=True,
            evidence_pack={
                "evidence_summary": {
                    "live_records": 2,
                    "replay_opportunities": 10,
                    "demo_records": 0,
                    "research_records": 1,
                    "no_trade_observations": 2,
                    "overall_confidence": "insufficient",
                    "gates_passed": False,
                },
                "confidence": {"overall_confidence": "insufficient"},
            },
        )
        assert pack["advisory_only"] is True
        assert pack["hard_locks"]["never_suggests_strategy_changes"] is True
        assert pack["executive_dashboard"]["operations_status"]["all_passed"] is False
        assert "daily_brief" in pack
        assert "checklist" in pack
        assert "end_of_day" in pack
        assert "weekly_review" in pack
        assert "monthly_review" in pack
        assert isinstance(pack["recommendations"], list)
