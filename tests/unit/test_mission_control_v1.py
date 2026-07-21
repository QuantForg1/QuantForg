"""Unit tests — QuantForg Mission Control."""

from __future__ import annotations

from app.domain.mission_control import MissionControlCenter, MissionFeeds
from app.domain.mission_control.config import MissionControlConfig


def test_status_not_monitoring_no_fabrication() -> None:
    center = MissionControlCenter()
    status = center.status()
    assert status["is_monitoring"] is False
    assert status["fabricates_metrics"] is False
    caps = status["capabilities"]
    assert caps["force_execution"] is False
    assert caps["bypass_risk"] is False
    assert caps["bypass_safety"] is False
    assert caps["monitoring_duplicate"] is False


def test_unavailable_when_feeds_missing() -> None:
    center = MissionControlCenter()
    dash = center.build_dashboard(MissionFeeds())
    panels = dash["panels"]
    assert panels["executive_status"]["status"] == "unavailable"
    assert panels["capital_overview"]["status"] == "unavailable"
    assert panels["live_positions"]["status"] == "unavailable"
    assert panels["xauusd_watchlist"]["status"] == "unavailable"
    assert dash["is_monitoring"] is False
    assert dash["fabricates_metrics"] is False


def test_executive_and_risk_from_control_center() -> None:
    center = MissionControlCenter()
    feeds = MissionFeeds(
        control_center={
            "system_status": "operational",
            "execution_mode": "SHADOW",
            "kill_switch": False,
            "gateway_status": "up",
            "mt5_status": "connected",
            "oms_orders_allowed": True,
            "config_version": "cfg-1",
            "strategy_version": "s-1",
            "unacked_alerts": 0,
            "risk": {
                "risk_per_trade_pct": "0.5",
                "max_daily_loss_pct": "2",
                "max_open_trades": 1,
                "daily_loss_exceeded": False,
            },
            "health": {"health_score": 97},
            "auto_trading": {"enabled": False, "status": "off"},
        },
        readiness={"risk_status": "ok", "health_score": 97},
    )
    dash = center.build_dashboard(feeds)
    assert dash["panels"]["executive_status"]["status"] == "available"
    assert dash["panels"]["risk_radar"]["data"]["max_open_trades"] == 1
    assert dash["panels"]["emergency_panel"]["data"]["kill_switch"] is False
    assert dash["panels"]["emergency_panel"]["data"]["actions_href"] == "/ops"
    assert dash["panels"]["system_health"]["data"]["gateway_status"] == "up"


def test_no_fake_capital_or_pnl() -> None:
    center = MissionControlCenter()
    dash = center.build_dashboard(
        MissionFeeds(
            control_center={"execution_mode": "SHADOW", "kill_switch": False},
            decision_history=[{"decision": "HOLD"}, {"decision": "REJECT"}],
        )
    )
    daily = dash["panels"]["daily_summary"]
    assert daily["status"] == "available"
    assert "pnl" not in daily["data"]
    assert "fabricated" not in str(daily["data"]).lower()
    assert daily["data"]["decision_counts"]["HOLD"] == 1


def test_operator_notes_auditable() -> None:
    center = MissionControlCenter()
    note = center.add_note(
        "Session start — shadow only", operator="alice", tags=["ops"]
    )
    assert note["note_id"].startswith("mcn_")
    listed = center.list_notes()
    assert listed["status"] == "available"
    assert listed["notes"][0]["text"].startswith("Session start")


def test_global_search_desks_and_notes() -> None:
    center = MissionControlCenter(MissionControlConfig())
    center.add_note("Watch spread on London open", operator="bob")
    result = center.search("terminal")
    assert result["status"] == "available"
    assert any(h["kind"] == "desk" for h in result["hits"])
    notes = center.search("london")
    assert any(h["kind"] == "note" for h in notes["hits"])


def test_empty_incidents_and_ai_health() -> None:
    center = MissionControlCenter()
    dash = center.build_dashboard(
        MissionFeeds(
            incidents=[],
            decision_intelligence={"product": "DI", "version": "1"},
            ai_robot={"product": "Robot", "version": "1"},
            positions=[],
            capital={"balance": 10000, "equity": 10000},
            xauusd={"bid": 2300.1, "ask": 2300.4, "symbol": "XAUUSD"},
        )
    )
    assert dash["panels"]["incident_center"]["status"] == "empty"
    assert dash["panels"]["ai_health"]["data"]["module_count"] == 2
    assert dash["panels"]["live_positions"]["status"] == "empty"
    assert dash["panels"]["capital_overview"]["data"]["equity"] == 10000
    assert dash["panels"]["xauusd_watchlist"]["data"]["symbol"] == "XAUUSD"
    assert dash["panels"]["floating_action_bar"]["status"] == "available"
