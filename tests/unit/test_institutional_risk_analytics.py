"""Unit tests — Institutional Risk Analytics Platform (read-only)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.institutional_risk_analytics.analytics import (
    build_alerts,
    build_concentration,
    build_core_metrics,
    build_correlation,
    build_drawdown_analytics,
    build_exposure,
    build_scenario_risk,
    build_stress_loss,
    build_tail_risk,
)
from app.domain.institutional_risk_analytics.models import ISOLATION_FLAGS
from app.domain.institutional_risk_analytics.platform import InstitutionalRiskAnalytics
from app.domain.institutional_risk_analytics.store import IrapStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "trade_count": 40,
                "sections": {
                    "performance": {
                        "profit_factor": 1.5,
                        "win_rate_pct": 52.0,
                        "expectancy": 2.0,
                        "average_win": 40,
                        "average_loss": 30,
                        "sharpe_ratio": 0.8,
                        "sortino_ratio": 1.1,
                        "calmar_ratio": 0.6,
                        "net_profit": 200,
                        "trade_count": 40,
                    },
                    "risk": {
                        "max_drawdown_pct": 16.0,
                        "current_drawdown_pct": 12.0,
                        "ulcer_index": 9.0,
                        "avg_exposure_pct": 40,
                    },
                    "behavior": {
                        "session_performance": {
                            "london": {"count": 25, "win_rate": 60, "total_pnl": 150},
                            "tokyo": {"count": 5, "win_rate": 30, "total_pnl": -40},
                            "new_york": {"count": 10, "win_rate": 50, "total_pnl": 20},
                        }
                    },
                },
            },
            "idw": {
                "trades": [
                    {"symbol": "XAUUSD", "pnl": 20},
                    {"symbol": "XAUUSD", "pnl": -15},
                    {"symbol": "XAUUSD", "pnl": 30},
                    {"symbol": "EURUSD", "pnl": -10},
                    {"symbol": "XAUUSD", "pnl": -80},
                    {"symbol": "XAUUSD", "pnl": 12},
                ]
            },
            "ise": {
                "simulations": [
                    {
                        "simulation_id": "s1",
                        "scenario": "volatility_spike",
                        "mode": "Historical Stress Test",
                        "metrics": {
                            "drawdown": 28,
                            "profit_factor": 0.9,
                            "win_rate": 40,
                        },
                    },
                    {
                        "simulation_id": "s2",
                        "scenario": "gap",
                        "metrics": {"drawdown": 35, "profit_factor": 0.7},
                    },
                ]
            },
            "cvf": {"confidence": {"confidence": 55}},
            "eqs": {"execution_score": {"overall_execution_score": 70}},
            "res": {"reliability_score": {"overall_reliability_score": 75}},
            "qkg": {},
            "sic": {},
        },
        "availability": {"portfolio": True, "idw": True, "ise": True},
        "source_count": 3,
    }


class TestIrapAnalytics:
    def test_metrics_var_cvar(self) -> None:
        m = build_core_metrics(_ctx())
        assert m["sharpe_ratio"] is not None
        assert m["maximum_drawdown"] == 16.0
        assert m["value_at_risk"] is not None
        assert m["conditional_var"] is not None
        assert m["never_modifies_production"] is True

    def test_exposure_drawdown_alerts(self) -> None:
        ctx = _ctx()
        exposure = build_exposure(ctx)
        assert exposure["by_session"]
        conc = build_concentration(ctx, exposure)
        assert conc["symbol_hhi"] is not None
        dd = build_drawdown_analytics(ctx)
        assert dd["drawdown_trend"] in {"increasing", "stable"}
        scenario = build_scenario_risk(ctx)
        stress = build_stress_loss(ctx, scenario)
        assert stress["max_stress_drawdown"] is not None
        tail = build_tail_risk(build_core_metrics(ctx))
        alerts = build_alerts(
            drawdown=dd,
            concentration=conc,
            exposure=exposure,
            capital={"allocations": list(exposure["by_session"].values())},
            tail=tail,
            metrics=build_core_metrics(ctx),
        )
        assert alerts
        for a in alerts:
            assert a["read_only"] is True
            assert a["never_triggers_automation"] is True
        corr = build_correlation(ctx)
        assert corr["session_matrix"]


class TestIrapPlatform:
    def test_isolation_and_perf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_risk_parameters"] is False
        assert ISOLATION_FLAGS["approves_releases"] is False
        irap = InstitutionalRiskAnalytics(store=IrapStore(path=tmp_path / "irap.json"))
        monkeypatch.setattr(
            "app.domain.institutional_risk_analytics.platform.gather_risk_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = irap.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["metrics"]["profit_factor"] is not None
        assert elapsed < 45
