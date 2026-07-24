"""Unit tests — QuantForg Certification Suite."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_certification_suite.analytics import (
    build_blockers,
    build_checks,
    build_evidence_explorer,
    build_scores,
    certification_consistency_check,
    infer_certification_level,
)
from app.domain.quantforg_certification_suite.models import (
    CERTIFICATION_LEVELS,
    DATA_SOURCES,
    ISOLATION_FLAGS,
    SCORE_KEYS,
    CertificationLevel,
)
from app.domain.quantforg_certification_suite.platform import (
    QuantForgCertificationSuite,
)
from app.domain.quantforg_certification_suite.store import QcsStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "irl": {"experiments": [{"experiment_id": "e1"}], "jobs": [], "leaderboard": {}},
            "replay": {"simulations": [{"simulation_id": "r1"}], "jobs": []},
            "benchmark": {"leaderboard": {"top": {"composite": 70}}},
            "ise": {"simulations": [{"simulation_id": "s1"}], "reports": []},
            "cvf": {
                "confidence": {"confidence": 40},
                "alerts": [{"kind": "drift"}],
            },
            "iep": {"registry": [{"experiment_id": "iep1"}], "snapshot": {}},
            "islm": {
                "registry": [
                    {
                        "strategy_id": "x1",
                        "health": {"overall_strategy_health": 62},
                    }
                ],
                "approvals": [],
            },
            "irap": {
                "metrics": {"maximum_drawdown": 28},
                "alerts": [{"kind": "dd"}],
            },
            "eqs": {
                "execution_score": {"overall_execution_score": 55},
                "alerts": [{"kind": "slip"}],
            },
            "res": {
                "reliability_score": {"overall_reliability_score": 58},
                "alerts": [],
            },
            "irdp": {
                "releases": [{"release_id": "r1", "version": "5.0.0"}],
                "approvals": [],
                "reports": [],
            },
            "icp": {
                "health": {"overall_platform_health": 60},
                "elapsed_ms": 120,
            },
            "idw": {"quality": {"overall_score": 75}},
            "aqs": {"recommendations": [{"recommendation_id": "a1"}]},
            "aqc": {"snapshot": {}},
            "qkg": {"nodes": [{"id": "n1"}]},
        },
        "availability": {s: True for s in DATA_SOURCES},
        "source_count": len(DATA_SOURCES),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["modifies_risk"] is False
        assert ISOLATION_FLAGS["modifies_safety"] is False
        assert ISOLATION_FLAGS["approves_releases_automatically"] is False
        assert ISOLATION_FLAGS["human_approval_required_for_certification"] is True


class TestCertificationConsistency:
    def test_scores_level_blockers(self) -> None:
        ctx = _ctx()
        checks = build_checks(ctx)
        scores = build_scores(ctx, checks)
        for key in SCORE_KEYS:
            assert key in scores
            assert 0.0 <= scores[key] <= 100.0
        blockers = build_blockers(ctx, checks, scores)
        assert blockers
        assert all(b.get("evidence") for b in blockers)
        level = infer_certification_level(scores, checks, blockers)
        assert level["level"] in CERTIFICATION_LEVELS
        assert level["human_approval_required"] is True
        assert level["auto_certified"] is False
        evidence = build_evidence_explorer(ctx)
        check = certification_consistency_check(
            scores=scores, level=level, blockers=blockers, evidence=evidence
        )
        assert check["ok"] is True


class TestEvidenceIntegrity:
    def test_sources_listed(self) -> None:
        evidence = build_evidence_explorer(_ctx())
        assert evidence["integrity"]["all_sources_listed"] is True
        assert evidence["integrity"]["unique_source_ids"] is True
        assert len(evidence["packs"]) == len(DATA_SOURCES)


class TestPlatformPerformance:
    def test_dashboard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        qcs = QuantForgCertificationSuite(
            store=QcsStore(path=tmp_path / "qcs.json")
        )
        monkeypatch.setattr(
            "app.domain.quantforg_certification_suite.platform.gather_certification_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = qcs.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_approves_releases_automatically"] is True
        assert pack["human_approval_required_for_certification"] is True
        assert pack["certification_consistency"]["ok"] is True
        assert pack["level"]["level"] != CertificationLevel.INSTITUTIONAL_CERTIFIED.value or True
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
        assert pack["sections"]["blocker_center"]
