"""Unit tests — Release Candidate RC1."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.release_candidate.capital_advisor import (
    advise_capital_scale,
)
from app.domain.institutional_trading.release_candidate.checklist import (
    run_production_checklist,
)
from app.domain.institutional_trading.release_candidate.config import (
    CHECKLIST_ITEMS,
    DEFAULT_RC1_CONFIG,
    SMOKE_CHECKS,
)
from app.domain.institutional_trading.release_candidate.go_live_score import (
    compute_go_live_score,
)
from app.domain.institutional_trading.release_candidate.reports import (
    report_to_csv,
)
from app.domain.institutional_trading.release_candidate.smoke import (
    run_production_smoke,
)
from app.domain.institutional_trading.release_candidate.venues import (
    VenueStatsStore,
)


@pytest.mark.unit
def test_rc1_hard_locks() -> None:
    assert DEFAULT_RC1_CONFIG.smoke_never_places_orders is True
    assert DEFAULT_RC1_CONFIG.never_auto_scale_capital is True
    assert DEFAULT_RC1_CONFIG.never_mix_trading_venues is True
    assert DEFAULT_RC1_CONFIG.no_new_strategies is True
    assert DEFAULT_RC1_CONFIG.no_experimental_production_logic is True


@pytest.mark.unit
def test_production_checklist_statuses() -> None:
    result = run_production_checklist()
    assert result["overall"] in {"PASS", "WARNING", "FAIL"}
    assert result["affects_production"] is False
    ids = {i["id"] for i in result["items"]}
    for cid in CHECKLIST_ITEMS:
        assert cid in ids
    for item in result["items"]:
        assert item["status"] in {"PASS", "WARNING", "FAIL"}


@pytest.mark.unit
def test_smoke_never_places_orders() -> None:
    result = run_production_smoke(use_live_probes=False)
    assert result["places_orders"] is False
    assert result["smoke_never_places_orders"] is True
    ids = {c["id"] for c in result["checks"]}
    for sid in SMOKE_CHECKS:
        assert sid in ids
    assert all(c.get("places_orders") is False for c in result["checks"])


@pytest.mark.unit
def test_go_live_score_threshold() -> None:
    score = compute_go_live_score(
        checklist={"counts": {"PASS": 13, "WARNING": 0, "FAIL": 0}},
        validation={
            "metrics": {
                "consecutive_successful_trading_days": 28,
                "average_latency_ms": 50,
                "error_rate": 0.01,
            }
        },
        live_stats={
            "live_statistics": {
                "win_rate": 58,
                "profit_factor": 1.5,
                "current_drawdown": 3,
            }
        },
        smoke={"counts": {"PASS": 7, "WARNING": 0, "FAIL": 0}},
    )
    assert 0 <= score["score"] <= 100
    assert score["auto_scale_capital"] is False
    assert "threshold" in score


@pytest.mark.unit
def test_venues_never_mix(tmp_path) -> None:
    store = VenueStatsStore()
    store._path = tmp_path / "venues.json"
    store.record("paper", {"trades": 10, "win_rate": 55, "pnl": 20})
    store.record("demo", {"trades": 20, "win_rate": 52, "pnl": 40})
    store.record("live", {"trades": 5, "win_rate": 50, "pnl": 10})
    snap = store.snapshot()
    assert snap["never_mix"] is True
    assert snap["venues"]["paper"]["trades"] == 10
    assert snap["venues"]["demo"]["trades"] == 20
    assert snap["venues"]["live"]["trades"] == 5
    with pytest.raises(ValueError):
        store.record("mixed", {"trades": 1})


@pytest.mark.unit
def test_capital_advisor_never_auto_applies() -> None:
    advice = advise_capital_scale(
        current_capital=200,
        win_rate=55,
        drawdown_pct=4,
        sharpe=1.0,
        go_live_score=85,
    )
    assert advice["never_auto_scale_capital"] is True
    assert advice["auto_applied"] is False
    assert advice["eligible"] is True
    assert advice["suggested_next_capital"] == 500.0

    blocked = advise_capital_scale(
        current_capital=200,
        win_rate=40,
        drawdown_pct=15,
        go_live_score=50,
    )
    assert blocked["eligible"] is False
    assert blocked["suggested_next_capital"] is None


@pytest.mark.unit
def test_report_csv_export() -> None:
    report = {
        "period": "daily",
        "sections": {"performance": {"win_rate": 55}},
    }
    csv_text = report_to_csv(report)
    assert "performance" in csv_text
    assert "win_rate" in csv_text


@pytest.mark.unit
def test_rc1_dashboard_shape() -> None:
    from app.application.services.release_candidate import build_rc1_dashboard

    dash = build_rc1_dashboard(current_capital=200)
    assert dash["version"].startswith("release-candidate-rc1")
    assert dash["safeguards"]["smoke_never_places_orders"] is True
    assert dash["safeguards"]["never_auto_scale_capital"] is True
    for key in (
        "checklist",
        "live_statistics",
        "rc_validation",
        "go_live_score",
        "venues",
        "capital_advisor",
        "documentation",
    ):
        assert key in dash
