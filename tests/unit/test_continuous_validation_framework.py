"""Unit tests — Continuous Validation Framework (read-only)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.continuous_validation_framework.analytics import (
    build_evidence_chains,
    build_parameter_stability,
    build_regime_validation,
    build_replay_vs_live,
    build_statistical_confidence,
    build_strategy_drift,
    build_validation_alerts,
)
from app.domain.continuous_validation_framework.models import ISOLATION_FLAGS, REGIMES
from app.domain.continuous_validation_framework.platform import (
    ContinuousValidationFramework,
)
from app.domain.continuous_validation_framework.store import CvfStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "trade_count": 40,
                "sections": {
                    "performance": {
                        "profit_factor": 1.2,
                        "win_rate_pct": 48.0,
                        "expectancy": 1.5,
                        "average_rr": 1.1,
                        "trade_count": 40,
                    },
                    "risk": {"max_drawdown_pct": 16.0, "ulcer_index": 14.0},
                    "behavior": {
                        "average_holding_time_sec": 1800,
                        "session_performance": {
                            "london": {"win_rate": 62.0},
                            "tokyo": {"win_rate": 30.0},
                        },
                    },
                },
            },
            "irl": {
                "leaderboard": {
                    "rows": [
                        {
                            "uuid": "e1",
                            "name": "Replay A",
                            "profit_factor": 2.0,
                            "win_rate": 55.0,
                            "expectancy": 4.0,
                            "maximum_drawdown_pct": 8.0,
                            "total_trades": 200,
                            "average_rr": 1.4,
                        }
                    ]
                },
                "jobs": [{"id": "j1", "name": "replay-job"}],
                "benchmark": {
                    "production_baseline": {
                        "profit_factor": 1.8,
                        "win_rate": 52,
                        "total_trades": 150,
                    }
                },
                "experiments": [],
            },
            "regime": {
                "current": {
                    "current_regime": "TRENDING",
                    "historical_performance": {
                        "win_rate": 0.55,
                        "profit_factor": 1.9,
                    },
                }
            },
            "idw": {"regimes": [], "trades": [], "signals": [], "research": []},
            "aqs": {
                "recommendations": [
                    {
                        "id": "r1",
                        "scores": {"research_confidence_score": 75},
                    }
                ],
                "reports": [],
            },
            "aqc": {"conversations": []},
            "eqs": {"execution_score": {"latency": 40, "overall_execution_score": 50}},
            "res": {},
            "qkg": {"stats": {"node_count": 20}},
            "sic": {},
        },
        "availability": {"portfolio": True, "irl": True, "regime": True},
        "source_count": 3,
    }


class TestCvfAnalytics:
    def test_replay_vs_live_and_drift(self) -> None:
        ctx = _ctx()
        rvl = build_replay_vs_live(ctx)
        assert rvl["comparison"]
        assert any(c["metric"] == "profit_factor" for c in rvl["comparison"])
        drift = build_strategy_drift(ctx, rvl)
        assert drift["drift_count"] >= 1
        assert drift["never_modifies_production"] is True

    def test_regimes_params_confidence_alerts_evidence(self) -> None:
        ctx = _ctx()
        rvl = build_replay_vs_live(ctx)
        drift = build_strategy_drift(ctx, rvl)
        regimes = build_regime_validation(ctx)
        assert len(regimes["regimes"]) == len(REGIMES)
        params = build_parameter_stability(ctx)
        assert params["never_changes_thresholds"] is True
        conf = build_statistical_confidence(
            ctx, replay_vs_live=rvl, drift=drift, parameter_stability=params
        )
        assert 0 <= conf["confidence"] <= 100
        assert conf["sample_size"] > 0
        alerts = build_validation_alerts(
            ctx,
            drift=drift,
            regime_validation=regimes,
            confidence=conf,
            replay_vs_live=rvl,
        )
        assert alerts
        for a in alerts:
            assert a["read_only"] is True
            assert a["never_triggers_automation"] is True
        chains = build_evidence_chains(
            ctx, alerts=alerts, replay_vs_live=rvl, confidence=conf
        )
        assert chains
        assert chains[0]["historical_baseline"] is not None
        assert "knowledge_graph_links" in chains[0]


class TestCvfPlatform:
    def test_isolation_and_perf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["approves_promotions"] is False
        assert ISOLATION_FLAGS["modifies_thresholds"] is False
        cvf = ContinuousValidationFramework(store=CvfStore(path=tmp_path / "cvf.json"))
        monkeypatch.setattr(
            "app.domain.continuous_validation_framework.platform.gather_validation_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = cvf.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["never_approves_promotions"] is True
        assert dash["confidence"]["confidence"] is not None
        assert elapsed < 45
