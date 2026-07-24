"""Unit tests — Institutional Control Plane."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.institutional_control_plane.analytics import (
    aggregation_consistency_check,
    build_dependency_map,
    build_evidence_center,
    build_executive_alerts,
    build_global_timeline,
    build_health_scores,
    build_reports,
)
from app.domain.institutional_control_plane.models import (
    HEALTH_SCORE_KEYS,
    ISOLATION_FLAGS,
    SUBSYSTEMS,
)
from app.domain.institutional_control_plane.platform import InstitutionalControlPlane
from app.domain.institutional_control_plane.store import IcpStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "icc": {
                "executive_kpis": {"trading_health": 70},
                "sections": {
                    "alerts": {
                        "items": [
                            {
                                "kind": "ICC notice",
                                "severity": "info",
                                "detail": "ok",
                            }
                        ]
                    },
                    "operational_timeline": {
                        "events": [
                            {
                                "kind": "ops",
                                "title": "heartbeat",
                                "at": "2026-07-24T00:00:00Z",
                            }
                        ]
                    },
                },
            },
            "idw": {"quality": {"overall_score": 80}},
            "cvf": {
                "confidence": {"confidence": 42},
                "alerts": [{"kind": "drift", "severity": "warning", "detail": "low"}],
            },
            "ise": {
                "simulations": [{"simulation_id": "s1"}, {"simulation_id": "s2"}],
                "reports": [],
            },
            "iep": {
                "registry": [
                    {
                        "experiment_id": "e1",
                        "title": "gate",
                        "lifecycle_state": "AI Review",
                        "hypothesis": "h",
                        "statistics": {"generalization_score": 66},
                        "updated_at": "2026-07-24T01:00:00Z",
                    }
                ],
                "snapshot": {},
            },
            "islm": {
                "registry": [
                    {
                        "strategy_id": "x1",
                        "name": "XAU",
                        "lifecycle_state": "Monitoring",
                        "updated_at": "2026-07-24T02:00:00Z",
                    }
                ],
                "approvals": [],
            },
            "irap": {
                "metrics": {"maximum_drawdown": 25, "sharpe_ratio": 0.5},
                "alerts": [
                    {"kind": "High drawdown", "severity": "high", "detail": "25%"}
                ],
            },
            "eqs": {
                "execution_score": {"overall_execution_score": 48},
                "alerts": [
                    {"kind": "slippage", "severity": "warning", "detail": "wide"}
                ],
            },
            "res": {
                "reliability_score": {"overall_reliability_score": 72},
                "alerts": [{"kind": "incident", "severity": "medium", "detail": "x"}],
            },
            "irdp": {
                "releases": [
                    {
                        "release_id": "r1",
                        "version": "4.0.0",
                        "status": "awaiting_approval",
                        "updated_at": "2026-07-24T03:00:00Z",
                    }
                ],
                "approvals": [],
            },
            "aqs": {"recommendations": [{"recommendation_id": "a1"}]},
            "aqc": {"snapshot": {"sessions": 1}},
            "qkg": {"nodes": [{"id": "n1"}], "stats": {"node_count": 1}},
        },
        "availability": {s: True for s in SUBSYSTEMS},
        "source_count": len(SUBSYSTEMS),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategy"] is False
        assert ISOLATION_FLAGS["modifies_risk"] is False
        assert ISOLATION_FLAGS["modifies_releases"] is False
        assert ISOLATION_FLAGS["approves_experiments"] is False
        assert ISOLATION_FLAGS["approves_lifecycle_transitions"] is False


class TestAggregationConsistency:
    def test_health_and_alerts(self) -> None:
        health = build_health_scores(_ctx())
        for key in HEALTH_SCORE_KEYS:
            assert key in health
            assert 0.0 <= health[key] <= 100.0
        alerts = build_executive_alerts(_ctx(), health)
        assert alerts
        assert all(a.get("evidence_link") for a in alerts)
        evidence = build_evidence_center(_ctx())
        check = aggregation_consistency_check(
            health=health, alerts=alerts, evidence=evidence
        )
        assert check["ok"] is True


class TestEvidenceIntegrity:
    def test_timeline_deps_reports(self) -> None:
        ctx = _ctx()
        health = build_health_scores(ctx)
        alerts = build_executive_alerts(ctx, health)
        timeline = build_global_timeline(ctx)
        deps = build_dependency_map(ctx)
        evidence = build_evidence_center(ctx)
        assert len(deps["nodes"]) == len(SUBSYSTEMS)
        assert evidence["integrity"]["all_subsystems_listed"] is True
        assert any(e.get("kind") == "release" for e in timeline)
        assert any(e.get("kind") == "experiment" for e in timeline)
        reports = build_reports(
            health=health,
            alerts=alerts,
            timeline=timeline,
            dependencies=deps,
            evidence=evidence,
        )
        assert "executive_daily_brief" in reports
        assert "quarterly_executive_report" in reports


class TestPlatformPerformance:
    def test_dashboard_fast_with_mocked_gather(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        icp = InstitutionalControlPlane(store=IcpStore(path=tmp_path / "icp.json"))
        monkeypatch.setattr(
            "app.domain.institutional_control_plane.platform.gather_control_plane_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = icp.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["aggregation_consistency"]["ok"] is True
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
