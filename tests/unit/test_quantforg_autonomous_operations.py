"""Unit tests — QuantForg Autonomous Operations Center."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_autonomous_operations.analytics import (
    build_evidence_explorer,
    build_executive_scores,
    build_operational_health,
    build_recommendations,
    build_watch_modules,
    build_work_queue,
    evidence_integrity_check,
    recommendation_consistency_check,
)
from app.domain.quantforg_autonomous_operations.models import (
    DATA_SOURCES,
    EXECUTIVE_SCORE_KEYS,
    ISOLATION_FLAGS,
    RECOMMENDATION_KINDS,
)
from app.domain.quantforg_autonomous_operations.platform import (
    QuantForgAutonomousOperationsCenter,
)
from app.domain.quantforg_autonomous_operations.store import AocStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "icp": {
                "health": {"overall_platform_health": 62},
                "alerts": [{"kind": "ops", "severity": "warning"}],
            },
            "qcs": {
                "level": {"level": "Not Ready"},
                "scores": {"overall_institutional_readiness_score": 48},
                "blockers": [{"kind": "Validation drift"}],
            },
            "qpm": {
                "metrics": {"portfolio_confidence_score": 55},
                "health": {"overall_portfolio_health": 58},
                "recommendations": [],
            },
            "irap": {
                "metrics": {"maximum_drawdown": 26},
                "alerts": [{"kind": "High drawdown"}],
            },
            "islm": {"registry": [{"strategy_id": "x1", "lifecycle_state": "Research"}], "approvals": []},
            "iep": {
                "registry": [
                    {
                        "experiment_id": "e1",
                        "title": "gate",
                        "lifecycle_state": "Human Decision",
                    }
                ]
            },
            "ise": {"simulations": [{"simulation_id": "s1", "mode": "Monte Carlo"}]},
            "cvf": {"confidence": {"confidence": 38}, "alerts": [{"kind": "drift"}]},
            "eqs": {
                "execution_score": {"overall_execution_score": 70},
                "alerts": [{"kind": "a"}, {"kind": "b"}],
            },
            "res": {
                "reliability_score": {"overall_reliability_score": 72},
                "alerts": [],
            },
            "aqs": {"recommendations": [{"recommendation_id": "a1", "title": "tune"}]},
            "aqc": {"snapshot": {}},
            "qkg": {},
        },
        "availability": {s: (s != "qkg") for s in DATA_SOURCES},
        "source_count": len(DATA_SOURCES) - 1,
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["modifies_risk"] is False
        assert ISOLATION_FLAGS["modifies_safety"] is False
        assert ISOLATION_FLAGS["approves_releases"] is False
        assert ISOLATION_FLAGS["allocates_capital"] is False
        assert ISOLATION_FLAGS["deploys_strategies"] is False
        assert ISOLATION_FLAGS["performs_automatic_remediation"] is False
        assert ISOLATION_FLAGS["preserves_existing_safety_guarantees"] is True


class TestRecommendationConsistency:
    def test_recs_and_queue(self) -> None:
        ctx = _ctx()
        health = build_operational_health(ctx)
        watches = build_watch_modules(ctx)
        recs = build_recommendations(ctx, watches)
        assert recs
        assert all(r["kind"] in RECOMMENDATION_KINDS for r in recs)
        assert all(r.get("requires_human_approval") for r in recs)
        assert all(r.get("auto_applied") is False for r in recs)
        assert all(r.get("never_remediates_automatically") for r in recs)
        assert recommendation_consistency_check(recs)["ok"] is True
        queue = build_work_queue(recs)
        assert queue
        assert queue[0]["auto_remediation"] is False
        scores = build_executive_scores(ctx, health, watches)
        for key in EXECUTIVE_SCORE_KEYS:
            assert key in scores
            assert 0.0 <= scores[key] <= 100.0
        evidence = build_evidence_explorer(ctx)
        assert evidence_integrity_check(
            evidence=evidence, scores=scores, queue=queue
        )["ok"] is True


class TestPlatformPerformance:
    def test_dashboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aoc = QuantForgAutonomousOperationsCenter(
            store=AocStore(path=tmp_path / "aoc.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_autonomous_operations.platform.gather_operations_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = aoc.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_performs_automatic_remediation"] is True
        assert pack["preserves_existing_safety_guarantees"] is True
        assert pack["recommendation_consistency"]["ok"] is True
        assert pack["evidence_integrity"]["ok"] is True
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
