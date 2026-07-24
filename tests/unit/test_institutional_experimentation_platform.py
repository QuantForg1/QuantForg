"""Unit tests — Institutional Experimentation Platform."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_experimentation_platform.analytics import (
    build_registry_from_sources,
    build_reports,
    compute_experiment_statistics,
    infer_lifecycle,
    statistical_consistency_check,
)
from app.domain.institutional_experimentation_platform.models import (
    ISOLATION_FLAGS,
    LIFECYCLE_ORDER,
    ExperimentLifecycle,
)
from app.domain.institutional_experimentation_platform.platform import (
    InstitutionalExperimentationPlatform,
)
from app.domain.institutional_experimentation_platform.store import IepStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "portfolio": {
                "trade_count": 40,
                "sections": {
                    "performance": {
                        "expectancy": 2.0,
                        "profit_factor": 1.4,
                        "trade_count": 40,
                    }
                },
            },
            "irl": {
                "experiments": [
                    {
                        "experiment_id": "e1",
                        "name": "gate-relax",
                        "hypothesis": "Lowering Q improves expectancy",
                        "status": "Completed",
                        "composite": 72,
                        "params": {"candidate_quality_formula": "q70"},
                        "statistics": {"total_trades": 40},
                    },
                    {
                        "experiment_id": "e2",
                        "name": "session-filter",
                        "composite": 65,
                    },
                    {
                        "experiment_id": "e3",
                        "name": "atr-widen",
                        "composite": 58,
                    },
                ],
                "leaderboard": {},
                "jobs": [],
            },
            "ise": {
                "simulations": [
                    {
                        "simulation_id": "s1",
                        "mode": "Historical Replay",
                        "metrics": {"drawdown": 12},
                    },
                    {
                        "simulation_id": "s2",
                        "scenario": "monte_carlo",
                        "metrics": {"drawdown": 18},
                    },
                ]
            },
            "cvf": {"confidence": {"confidence": 62}, "alerts": []},
            "irap": {
                "metrics": {"maximum_drawdown": 15, "sharpe_ratio": 0.8},
                "alerts": [],
            },
            "aqs": {
                "recommendations": [
                    {"recommendation_id": "a1", "title": "review gate"}
                ]
            },
            "qkg": {
                "nodes": [
                    {"id": "n1", "label": "experiment gate", "type": "experiment"}
                ]
            },
            "sic": {},
            "islm": {"registry": []},
        },
        "availability": {"irl": True, "ise": True, "portfolio": True},
        "source_count": 3,
        "read_only": True,
    }


class TestLifecycleAndIsolation:
    def test_order(self) -> None:
        assert LIFECYCLE_ORDER[0] == ExperimentLifecycle.IDEA.value
        assert LIFECYCLE_ORDER[-1] == ExperimentLifecycle.ARCHIVE.value

    def test_infer(self) -> None:
        assert (
            infer_lifecycle({"hypothesis": "x"})
            == ExperimentLifecycle.HYPOTHESIS.value
        )
        assert (
            infer_lifecycle({"replay_results": [{}]})
            == ExperimentLifecycle.REPLAY.value
        )

    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["approves_experiments_automatically"] is False
        assert ISOLATION_FLAGS["promotes_experiments_automatically"] is False


class TestStatisticalConsistency:
    def test_stats_bounds(self) -> None:
        st = compute_experiment_statistics(
            sample_size=40,
            baseline_metric=1.0,
            variant_metric=1.4,
            baseline_sd=0.3,
            variant_sd=0.35,
        )
        assert 0.0 <= st["p_value"] <= 1.0
        assert 0.0 <= st["statistical_power"] <= 1.0
        assert st["sample_size"] == 40
        assert "confidence_interval" in st
        assert "effect_size" in st
        assert 0.0 <= st["generalization_score"] <= 100.0
        check = statistical_consistency_check(st)
        assert check["ok"] is True


class TestEvidenceIntegrity:
    def test_registry_reports(self) -> None:
        rows = build_registry_from_sources(_ctx())
        assert rows
        assert all(r.get("experiment_id") for r in rows)
        assert all(r.get("never_auto_approves") for r in rows)
        assert all(r.get("never_auto_promotes") for r in rows)
        primary = rows[0]
        assert primary["evidence"]["hypothesis"]
        assert primary["statistics"]
        reports = build_reports(
            experiments=rows,
            comparison={"ranked_by_evidence": primary.get("comparison")},
            decisions={"pending_human_decisions": []},
        )
        integrity = reports["evidence_report"]["integrity"]
        assert integrity["has_unique_ids"] is True
        assert integrity["lifecycle_in_enum"] is True
        assert integrity["statistics_keys_present"] is True


class TestPlatform:
    def test_dashboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        iep = InstitutionalExperimentationPlatform(
            store=IepStore(path=tmp_path / "iep.json")
        )
        monkeypatch.setattr(
            "app.domain.institutional_experimentation_platform.platform.gather_experiment_sources",
            _ctx,
        )
        pack = iep.dashboard()
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_approves_experiments_automatically"] is True
        assert pack["never_promotes_experiments_automatically"] is True
        assert pack["registry"]
        assert pack["sections"]["comparison_workspace"]
