"""Unit tests — QuantForg Portfolio Manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.quantforg_portfolio_manager.analytics import (
    build_capital_allocation,
    build_metrics,
    build_recommendations,
    build_strategy_ranking,
    evidence_integrity_check,
    recommendation_consistency_check,
)
from app.domain.quantforg_portfolio_manager.analytics import (
    build_capacity_analysis,
    build_correlation_analysis,
    build_diversification_analysis,
    build_portfolio_exposure,
    build_portfolio_health,
    build_portfolio_readiness,
)
from app.domain.quantforg_portfolio_manager.models import (
    ISOLATION_FLAGS,
    METRIC_KEYS,
    RECOMMENDATION_KINDS,
)
from app.domain.quantforg_portfolio_manager.platform import QuantForgPortfolioManager
from app.domain.quantforg_portfolio_manager.store import QpmStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "qsmr": {
                "registry": [
                    {
                        "strategy_id": "a",
                        "strategy_name": "Alpha",
                        "status": "Active",
                        "lifecycle": "Monitoring",
                        "certification_status": "Staging Ready",
                        "scores": {
                            "overall_strategy_score": 80,
                            "research_score": 70,
                            "validation_score": 75,
                            "risk_score": 65,
                            "execution_score": 78,
                            "certification_score": 72,
                        },
                    },
                    {
                        "strategy_id": "b",
                        "strategy_name": "Beta",
                        "status": "Research",
                        "lifecycle": "Research",
                        "certification_status": "Not Ready",
                        "scores": {
                            "overall_strategy_score": 40,
                            "research_score": 45,
                            "validation_score": 35,
                            "risk_score": 40,
                            "execution_score": 42,
                            "certification_score": 30,
                        },
                    },
                    {
                        "strategy_id": "c",
                        "strategy_name": "Gamma",
                        "status": "Active",
                        "lifecycle": "Production",
                        "certification_status": "Production Ready",
                        "scores": {
                            "overall_strategy_score": 88,
                            "research_score": 80,
                            "validation_score": 82,
                            "risk_score": 70,
                            "execution_score": 85,
                            "certification_score": 90,
                        },
                    },
                ]
            },
            "irap": {"metrics": {"sharpe_ratio": 1.1, "sortino_ratio": 1.4, "maximum_drawdown": 18}},
            "cvf": {"confidence": {"confidence": 68}},
            "ise": {"simulations": [{"simulation_id": "s1"}]},
            "iep": {"registry": []},
            "islm": {"registry": []},
            "eqs": {"execution_score": {"overall_execution_score": 76}},
            "res": {"reliability_score": {"overall_reliability_score": 74}},
            "qcs": {
                "level": {"level": "Staging Ready"},
                "scores": {"overall_institutional_readiness_score": 70},
            },
            "icp": {"health": {"risk_health": 65}},
        },
        "availability": {k: True for k in (
            "qsmr", "irap", "cvf", "ise", "iep", "islm", "eqs", "res", "qcs", "icp"
        )},
        "source_count": 10,
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["changes_strategy_parameters"] is False
        assert ISOLATION_FLAGS["rebalances_automatically"] is False
        assert ISOLATION_FLAGS["allocates_capital_automatically"] is False
        assert ISOLATION_FLAGS["human_approval_required_for_actions"] is True


class TestRecommendationConsistency:
    def test_recommendations(self) -> None:
        ctx = _ctx()
        ranked = build_strategy_ranking(ctx)
        allocation = build_capital_allocation(ranked)
        exposure = build_portfolio_exposure(ranked, allocation)
        capacity = build_capacity_analysis(ranked, ctx)
        correlation = build_correlation_analysis(ranked)
        diversification = build_diversification_analysis(exposure, correlation)
        metrics = build_metrics(
            ctx,
            ranked=ranked,
            allocation=allocation,
            diversification=diversification,
            correlation=correlation,
            capacity=capacity,
        )
        for key in METRIC_KEYS:
            assert key in metrics
        recs = build_recommendations(ranked, metrics, allocation)
        assert recs
        assert all(r["kind"] in RECOMMENDATION_KINDS for r in recs)
        assert all(r.get("requires_human_approval") for r in recs)
        assert all(r.get("auto_applied") is False for r in recs)
        assert recommendation_consistency_check(recs)["ok"] is True
        assert evidence_integrity_check(
            ranked=ranked, allocation=allocation, metrics=metrics
        )["ok"] is True


class TestPlatform:
    def test_dashboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qpm = QuantForgPortfolioManager(store=QpmStore(path=tmp_path / "qpm.json"))
        monkeypatch.setattr(
            "app.domain.quantforg_portfolio_manager.platform.gather_portfolio_sources",
            _ctx,
        )
        pack = qpm.dashboard()
        assert pack["never_executes_trades"] is True
        assert pack["never_rebalances_automatically"] is True
        assert pack["never_allocates_capital_automatically"] is True
        assert pack["human_approval_required_for_actions"] is True
        assert pack["recommendation_consistency"]["ok"] is True
        assert pack["evidence_integrity"]["ok"] is True
        assert pack["capital_allocation"]["human_approval_required"] is True
        readiness = build_portfolio_readiness(
            _ctx(), pack["portfolio_health"], pack["strategy_ranking"]
        )
        assert "ready" in readiness
