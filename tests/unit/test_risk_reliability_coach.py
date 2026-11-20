"""Risk, reliability, and coach reports stay read-only and do not invent safety."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.reliability_center.report import (
    ComponentCheck,
    ProtectionInput,
    build_protection_report,
)
from app.domain.risk_intelligence.report import RiskInsightInput, build_risk_insight
from app.domain.trading_coach.answer import answer_question

pytestmark = [pytest.mark.unit]
_NOW = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)


def test_missing_equity_is_unknown_not_safe() -> None:
    report = build_risk_insight(RiskInsightInput(read_at=_NOW))
    assert report["equity"]["status"] == "unavailable"
    assert report["changes_risk_policy"] is False
    assert report["places_orders"] is False
    codes = {item["code"] for item in report["insights"]}
    assert "unavailable" in codes
    assert "elevated_open_risk" not in codes


def test_open_risk_near_the_supplied_limit_is_explained() -> None:
    report = build_risk_insight(
        RiskInsightInput(
            read_at=_NOW,
            source="account_snapshot",
            equity="10000",
            aggregate_open_risk_pct="8.5",
            open_risk_limit_pct="10",
            used_margin="80",
            free_margin="20",
            consecutive_losses=3,
        )
    )
    codes = {item["code"] for item in report["insights"]}
    assert "elevated_open_risk" in codes
    assert "margin_utilization" in codes
    assert "consecutive_losses" in codes
    assert report["margin_used_pct"]["value"] == "80.00"
    assert all(item["changes_settings"] is False for item in report["insights"])


def test_saved_credentials_are_not_a_connected_session() -> None:
    report = build_protection_report(
        ProtectionInput(
            read_at=_NOW,
            credentials_saved=True,
            session_connected=False,
            components=(
                ComponentCheck("mt5_gateway", "healthy", _NOW - timedelta(seconds=10)),
                ComponentCheck("worker", "healthy", _NOW - timedelta(minutes=10)),
            ),
        )
    )
    states = report["account_states"]
    assert states["credentials_saved"]["value"] is True
    assert states["session_connected"]["value"] is False
    by_name = {item["name"]: item["state"] for item in report["components"]}
    assert by_name["mt5_gateway"] == "healthy"
    assert by_name["worker"] == "unknown"
    assert report["restarts_gateway"] is False


def test_flags_default_off_and_routers_are_registered() -> None:
    from app.main import _OPERATOR_ONLY_ROUTER_MODULES, _ROUTER_SPECS
    from core.config.settings import Settings

    spec = dict(_ROUTER_SPECS)
    assert spec["risk_intelligence"] == "app.presentation.routers.risk_intelligence"
    assert spec["reliability_center"] == "app.presentation.routers.reliability_center"
    assert spec["trading_coach"] == "app.presentation.routers.trading_coach"
    for name in ("risk_intelligence", "reliability_center", "trading_coach"):
        assert name not in _OPERATOR_ONLY_ROUTER_MODULES
    for field in (
        "risk_intelligence_enabled",
        "reliability_center_enabled",
        "trading_coach_enabled",
    ):
        assert Settings.model_fields[field].default is False


def test_coach_refuses_a_missing_number_and_an_unknown_question() -> None:
    missing = answer_question("open_risk", {})
    assert missing["status"] == "unavailable"
    assert missing["answer"] is None
    assert missing["places_orders"] is False
    grounded = answer_question("open_risk", {"aggregate_open_risk_pct": "4.2"})
    assert grounded["status"] == "grounded"
    assert grounded["answer"] == "4.2"
    assert grounded["recommendation"] is False
    unknown = answer_question("place_order", {"aggregate_open_risk_pct": "4.2"})
    assert unknown["status"] == "unavailable"
    assert unknown["places_orders"] is False
