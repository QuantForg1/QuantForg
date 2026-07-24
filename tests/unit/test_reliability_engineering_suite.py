"""Unit tests — Reliability Engineering Suite (read-only)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.reliability_engineering_suite.analytics import (
    build_availability,
    build_evidence,
    build_failure_analysis,
    build_platform_health,
    build_recovery_analytics,
    build_reliability_score,
    build_service_reliability,
    classify_failure,
)
from app.domain.reliability_engineering_suite.models import (
    FAILURE_CLASSES,
    ISOLATION_FLAGS,
    SERVICE_NAMES,
)
from app.domain.reliability_engineering_suite.platform import ReliabilityEngineeringSuite
from app.domain.reliability_engineering_suite.store import ResStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "idw": {
                "oms": [{"status": "fail", "event": "oms_submit_failed"}],
                "gateway": [
                    {"event": "gateway timeout fail", "latency_ms": 400},
                    {"event": "reconnect"},
                ],
                "broker": [{"event": "broker disconnect fail"}],
                "diagnostics": [],
            },
            "icc": {
                "alerts": [
                    {"message": "scheduler failure detected", "subsystem": "scheduler"}
                ]
            },
            "diagnostics": {
                "cycles": [
                    {
                        "cycle_id": "c1",
                        "outcome": "strategy reject",
                        "block_reason": "quality fail",
                    }
                ]
            },
            "audit": [
                {
                    "event_type": "recovery_success",
                    "mttr_sec": 120,
                    "mttd_sec": 25,
                }
            ],
            "eqs": {"latency": 80, "overall_execution_score": 72},
            "qkg": {"stats": {"node_count": 12}},
            "rc1": {},
            "live_metrics": {
                "oms_failures": 2,
                "gateway_latency_ms": 55,
                "execution_latency_ms": 110,
                "risk_rejects": 1,
            },
        },
        "availability": {
            "idw": True,
            "icc": True,
            "diagnostics": True,
            "eqs": True,
            "qkg": True,
        },
        "source_count": 5,
    }


class TestResAnalytics:
    def test_classify_and_services(self) -> None:
        assert (
            classify_failure({"_domain": "gateway", "event": "gateway fail"})
            == "Gateway Failure"
        )
        services = build_service_reliability(_ctx())
        names = {s["service"] for s in services}
        for required in SERVICE_NAMES:
            assert required in names

    def test_failures_recovery_score(self) -> None:
        ctx = _ctx()
        failures = build_failure_analysis(ctx)
        assert failures["total_failures"] >= 1
        for c in FAILURE_CLASSES:
            assert c in failures["by_class"]
        recovery = build_recovery_analytics(ctx)
        assert recovery["mttd_sec"] is not None
        assert recovery["mttr_sec"] is not None
        services = build_service_reliability(ctx)
        availability = build_availability(ctx, services)
        assert "daily" in availability
        score = build_reliability_score(
            availability=availability,
            recovery=recovery,
            failures=failures,
            services=services,
            eqs_snapshot={"latency": 80},
        )
        assert 0 <= score["overall_reliability_score"] <= 100
        health = build_platform_health(
            score=score,
            availability=availability,
            services=services,
            failures=failures,
        )
        assert "active_incidents" in health
        ev = build_evidence(ctx)
        assert "audit_trail" in ev
        assert "knowledge_graph" in ev


class TestResPlatform:
    def test_isolation_and_perf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["triggers_automation"] is False
        assert ISOLATION_FLAGS["modifies_scheduler"] is False
        res = ReliabilityEngineeringSuite(store=ResStore(path=tmp_path / "res.json"))
        monkeypatch.setattr(
            "app.domain.reliability_engineering_suite.platform.gather_reliability_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = res.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["reliability_score"]["overall_reliability_score"] is not None
        assert elapsed < 45
