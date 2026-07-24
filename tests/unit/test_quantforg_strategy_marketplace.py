"""Unit tests — QuantForg Strategy Marketplace & Registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.quantforg_strategy_marketplace.analytics import (
    build_registry,
    build_reports,
    compare_strategies,
    discover,
    evidence_integrity_check,
    registry_consistency_check,
)
from app.domain.quantforg_strategy_marketplace.models import ISOLATION_FLAGS, SCORE_KEYS
from app.domain.quantforg_strategy_marketplace.platform import (
    QuantForgStrategyMarketplace,
)
from app.domain.quantforg_strategy_marketplace.store import QsmrStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "islm": {
                "registry": [
                    {
                        "strategy_id": "xauusd-primary",
                        "name": "XAUUSD Primary",
                        "owner": "desk",
                        "version": "1.2.0",
                        "lifecycle_state": "Monitoring",
                        "health": {
                            "research_score": 70,
                            "validation_score": 65,
                            "risk_score": 60,
                            "execution_score": 72,
                            "overall_strategy_health": 67,
                        },
                        "evidence": {
                            "research_history": [{"experiment_id": "e1"}],
                            "replay_results": [{"simulation_id": "r1"}],
                            "simulation_results": [{"simulation_id": "s1"}],
                            "cvf_findings": {"confidence": 70},
                            "risk_analytics": {"metrics": {"maximum_drawdown": 12}},
                            "release_history": [{"release_id": "rel1"}],
                            "knowledge_graph_links": [{"node_id": "n1"}],
                        },
                    }
                ],
                "approvals": [],
            },
            "irl": {
                "experiments": [
                    {
                        "experiment_id": "e2",
                        "name": "lab-alpha",
                        "composite": 68,
                    }
                ],
                "leaderboard": {"top": {"composite": 68}},
            },
            "ise": {
                "simulations": [
                    {
                        "simulation_id": "s1",
                        "mode": "Historical Replay",
                        "metrics": {},
                    },
                    {"simulation_id": "s2", "scenario": "monte_carlo"},
                ]
            },
            "cvf": {"confidence": {"confidence": 70}},
            "irap": {"metrics": {"maximum_drawdown": 12}},
            "eqs": {"execution_score": {"overall_execution_score": 74}},
            "qcs": {
                "level": {"level": "Staging Ready"},
                "scores": {"overall_institutional_readiness_score": 72},
            },
            "irdp": {"releases": [{"release_id": "rel1", "version": "5.1.0"}]},
            "iep": {"registry": [{"experiment_id": "iep1", "title": "exp"}]},
            "aqs": {"recommendations": []},
            "qkg": {"nodes": [{"id": "n1", "label": "XAU strategy", "type": "strategy"}]},
            "portfolio": {
                "sections": {
                    "performance": {"expectancy": 2.0, "profit_factor": 1.3},
                    "risk": {"max_drawdown_pct": 12},
                }
            },
        },
        "availability": {"islm": True, "irl": True, "ise": True, "qcs": True},
        "source_count": 4,
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["approves_certifications"] is False
        assert ISOLATION_FLAGS["deploys_strategies"] is False


class TestRegistryConsistency:
    def test_registry_and_scores(self) -> None:
        rows = build_registry(_ctx())
        assert rows
        assert all(r.get("strategy_id") for r in rows)
        assert all(r.get("never_deploys") for r in rows)
        for r in rows:
            for key in SCORE_KEYS:
                assert key in r["scores"]
                assert 0.0 <= r["scores"][key] <= 100.0
        check = registry_consistency_check(rows)
        assert check["ok"] is True


class TestEvidenceIntegrity:
    def test_evidence_and_discovery(self) -> None:
        rows = build_registry(_ctx())
        assert evidence_integrity_check(rows)["ok"] is True
        found = discover(rows, q="xau", sort_by="overall_strategy_score")
        assert found["count"] >= 1
        cmp = compare_strategies(rows)
        assert cmp["strategies"]
        reports = build_reports(rows)
        assert "strategy_registry" in reports
        assert "certification_summary" in reports


class TestPlatform:
    def test_dashboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qsmr = QuantForgStrategyMarketplace(
            store=QsmrStore(path=tmp_path / "qsmr.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_strategy_marketplace.platform.gather_marketplace_sources",
            _ctx,
        )
        pack = qsmr.dashboard()
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_strategies"] is True
        assert pack["never_deploys_strategies"] is True
        assert pack["never_approves_certifications"] is True
        assert pack["registry_consistency"]["ok"] is True
        assert pack["evidence_integrity"]["ok"] is True
        assert pack["sections"]["comparison_workspace"]
