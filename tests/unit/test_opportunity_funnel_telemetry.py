"""Opportunity funnel telemetry — observability only, never mutates gates."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.services.opportunity_funnel_telemetry import (
    classify_blocker_source,
    observe_funnel_cycle,
    reset_funnel_telemetry_for_tests,
    funnel_snapshot,
)
from app.application.services.strategy_diagnostics import (
    extract_cycle_diagnostics,
    reset_strategy_diagnostics_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.mark.unit
def test_blocker_source_maps_directional_edge() -> None:
    assert classify_blocker_source("WAIT_NO_DIRECTIONAL_EDGE") == "DIRECTION"
    assert classify_blocker_source("opportunity_score 64 < threshold 70") == "OPPORTUNITY"
    assert classify_blocker_source("WAIT_CHASE") == "SNIPER"
    assert classify_blocker_source("RISK_BLOCK") == "RISK"
    assert classify_blocker_source("") == "NONE"


@pytest.mark.unit
def test_histogram_does_not_claim_qualifying_on_current_wait_tape(
    tmp_path,
) -> None:
    reset_funnel_telemetry_for_tests(tmp_path / "funnel.json")
    for _ in range(5):
        observe_funnel_cycle(
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                "market_session": "london",
                "opportunity_score": 64,
                "directional_edge": 4,
                "buy_score": 42,
                "sell_score": 34,
                "ltf_buy_score": 28,
                "ltf_sell_score": 24,
                "decision_action": "WAIT",
                "setup_state": "CONFLICT",
                "first_authoritative_blocker": "WAIT_NO_DIRECTIONAL_EDGE",
                "blocker_source": "DIRECTION",
                "forwarded_to_oms": False,
            }
        )
    snap = funnel_snapshot()
    assert snap["advisory_only"] is True
    assert snap["mutates_engines"] is False
    assert snap["opportunity_threshold"] == 70
    assert snap["edge_margin"] == 5
    assert snap["totals"]["opportunity"]["60-69"] == 5
    assert snap["totals"]["edge"]["3-4"] == 5
    assert snap["totals"]["funnel"]["edge_ge_5"] == 0
    assert snap["totals"]["funnel"]["opportunity_ge_70"] == 0
    assert snap["totals"]["funnel"]["both_qualify"] == 0
    assert snap["totals"]["funnel"]["oms_forward"] == 0
    assert snap["totals"]["funnel"]["mt5_ticket"] == 0
    assert snap["totals"]["funnel"]["wait"] == 5
    assert snap["totals"]["funnel"]["buy_leading"] == 5
    assert snap["rates_pct"]["both_qualify"] == 0.0
    assert "1h" in snap["windows"]
    assert "3d" in snap["windows"]
    assert "7d" in snap["windows"]
    assert "14d" in snap["windows"]
    assert "30d" in snap["windows"]
    assert snap["windows"]["1h"]["n"] == 5
    assert snap["windows"]["1h"]["rates_pct"]["edge_ge_5"] == 0.0
    assert snap["windows"]["1h"]["rates_pct"]["opp_ge_60"] == 100.0
    assert snap["windows"]["1h"]["rates_pct"]["opp_ge_65"] == 0.0
    assert snap["windows"]["1h"]["rates_pct"]["opp_ge_70"] == 0.0
    assert snap["windows"]["1h"]["incomplete"] is False
    assert snap["windows"]["1h"]["stage_rates_pct"]["DIRECTION"] == 100.0
    assert snap["windows"]["1h"]["stage_rates_pct"]["OMS"] == 0.0
    assert snap["windows"]["1h"]["stage_rates_pct"]["MT5"] == 0.0
    assert snap["totals"]["funnel"]["opp_ge_60"] == 5
    assert snap["totals"]["funnel"]["opp_ge_70"] == 0
    assert snap["totals"]["funnel"]["edge_ge_3"] == 5
    assert snap["totals"]["funnel"]["edge_ge_5"] == 0


@pytest.mark.unit
def test_empty_histogram_window_is_incomplete_not_zero_opportunity(tmp_path) -> None:
    reset_funnel_telemetry_for_tests(tmp_path / "funnel.json")
    snap = funnel_snapshot()
    assert snap["windows"]["30d"]["n"] == 0
    assert snap["windows"]["30d"]["incomplete"] is True
    assert snap["windows"]["30d"]["rates_pct"]["opp_ge_70"] == 0.0
    assert snap["never_changes_thresholds"] is True
    assert snap["opportunity_threshold"] == 70


@pytest.mark.unit
def test_extract_persists_funnel_fields_without_take() -> None:
    reset_strategy_diagnostics_store()
    row = extract_cycle_diagnostics(
        snapshot=None,
        decision=None,
        cycle_outcome="wait",
        decision_action="WAIT",
        abort_reason="WAIT_NO_DIRECTIONAL_EDGE",
        market_context_diagnostics={
            "symbol": "XAUUSD_I",
            "buy_score": 42,
            "sell_score": 34,
            "ltf_buy_score": 28,
            "ltf_sell_score": 24,
            "directional_edge": 4,
            "opportunity_score": 64,
            "setup_state": "CONFLICT",
            "buy_families": ["structure", "zone"],
            "sell_families": ["structure"],
            "as_of": "2026-08-28T11:53:32Z",
            "data": "LIVE",
            "market_data_valid": True,
        },
        forwarded_to_oms=False,
    )
    assert row["advisory_only"] is True
    assert row["buy_score"] == 42
    assert row["sell_score"] == 34
    assert row["ltf_buy_score"] == 28
    assert row["ltf_sell_score"] == 24
    assert row["directional_edge"] == 4
    assert row["opportunity_score"] == 64
    assert row["setup_state"] == "CONFLICT"
    assert row["buy_families"] == ["structure", "zone"]
    assert row["sell_families"] == ["structure"]
    assert row["scan_as_of"] == "2026-08-28T11:53:32Z"
    assert row["data"] == "LIVE"
    assert row["forwarded_to_oms"] is False
    assert row["executed"] is False
    assert row["blocker_source"] == "DIRECTION"
    assert row["first_authoritative_blocker"]
    assert "WAIT_NO_DIRECTIONAL_EDGE" in str(row["first_authoritative_blocker"])
