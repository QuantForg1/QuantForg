"""Unit tests — Execution Quality Suite (read-only)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.execution_quality_suite.analytics import (
    build_alerts,
    build_broker_health,
    build_consistency,
    build_evidence_links,
    build_execution_score,
    build_execution_timelines,
    build_fill_quality,
    build_latency_analytics,
    build_slippage_analytics,
)
from app.domain.execution_quality_suite.models import ISOLATION_FLAGS, TIMELINE_STAGES
from app.domain.execution_quality_suite.platform import ExecutionQualitySuite
from app.domain.execution_quality_suite.store import EqsStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "journal": [
                {
                    "journal_id": "j1",
                    "order_id": "o1",
                    "timestamp": "2026-07-23T10:00:00Z",
                    "latency_ms": 120,
                    "gateway_latency_ms": 40,
                    "broker_latency_ms": 30,
                    "oms_latency_ms": 25,
                    "strategy_latency_ms": 15,
                    "gateway": "mt5",
                    "broker": "demo",
                    "symbol": "XAUUSD",
                    "side": "buy",
                    "price": "2400.5",
                    "expected_entry": 2400.0,
                    "actual_entry": 2400.5,
                    "slippage": "0.5",
                    "execution_result": "filled",
                    "stages": [
                        {"stage": "signal", "timestamp": "2026-07-23T09:59:50Z"},
                        {"stage": "risk", "timestamp": "2026-07-23T09:59:55Z"},
                        {"stage": "safety", "timestamp": "2026-07-23T09:59:56Z"},
                        {"stage": "oms", "timestamp": "2026-07-23T09:59:57Z"},
                        {"stage": "gateway", "timestamp": "2026-07-23T09:59:58Z"},
                        {"stage": "broker", "timestamp": "2026-07-23T09:59:59Z"},
                    ],
                },
                {
                    "journal_id": "j2",
                    "order_id": "o2",
                    "timestamp": "2026-07-23T11:00:00Z",
                    "latency_ms": 900,
                    "gateway": "mt5",
                    "broker": "demo",
                    "execution_result": "rejected",
                    "slippage": "-0.8",
                },
            ],
            "idw": {
                "oms": [{"latency_ms": 22}],
                "gateway": [{"latency_ms": 45}],
                "broker": [
                    {"event": "reconnect", "latency_ms": 60},
                    {"status": "fail", "latency_ms": 200},
                ],
                "execution": [],
                "trades": [],
            },
            "diagnostics": {"cycles": []},
            "icc": {},
            "portfolio": {},
            "audit": [{"id": "a1", "event_type": "execution_review"}],
            "qkg": {"stats": {"node_count": 10}},
            "live_metrics": {
                "execution_latency_ms": 100,
                "gateway_latency_ms": 35,
                "fills": 1,
                "rejects": 1,
                "oms_failures": 2,
            },
            "rc1": {"avg_gateway_latency_ms": 38},
        },
        "availability": {"journal": True, "idw": True},
        "source_count": 2,
    }


class TestEqsAnalytics:
    def test_timeline_stages(self) -> None:
        timelines = build_execution_timelines(_ctx())
        assert timelines
        stages = [s["stage"] for s in timelines[0]["timeline"]]
        assert stages == list(TIMELINE_STAGES)

    def test_latency_slippage_fills(self) -> None:
        ctx = _ctx()
        lat = build_latency_analytics(ctx)
        assert lat["total_execution_latency"]["sample_size"] >= 1
        assert lat["total_execution_latency"]["p95"] is not None
        slip = build_slippage_analytics(ctx)
        assert slip["sample_size"] >= 1
        assert slip["worst_slippage"] is not None
        fills = build_fill_quality(ctx)
        assert fills["attempts"] >= 1
        assert fills["execution_success_rate"] is not None

    def test_score_alerts_evidence(self) -> None:
        ctx = _ctx()
        lat = build_latency_analytics(ctx)
        slip = build_slippage_analytics(ctx)
        fills = build_fill_quality(ctx)
        cons = build_consistency(ctx, lat)
        broker = build_broker_health(ctx)
        score = build_execution_score(
            latency=lat,
            slippage=slip,
            fills=fills,
            consistency=cons,
            broker=broker,
        )
        assert 0 <= score["overall_execution_score"] <= 100
        alerts = build_alerts(
            latency=lat,
            slippage=slip,
            fills=fills,
            broker=broker,
            consistency=cons,
        )
        assert any(a["read_only"] for a in alerts) or alerts == []
        # high latency / failures should produce alerts
        assert alerts
        for a in alerts:
            assert a["never_triggers_automation"] is True
        ev = build_evidence_links(ctx)
        assert "oms_events" in ev
        assert "knowledge_graph" in ev


class TestEqsPlatform:
    def test_isolation_and_perf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_oms"] is False
        assert ISOLATION_FLAGS["modifies_gateway"] is False
        eqs = ExecutionQualitySuite(store=EqsStore(path=tmp_path / "eqs.json"))
        monkeypatch.setattr(
            "app.domain.execution_quality_suite.platform.gather_execution_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        dash = eqs.dashboard()
        elapsed = time.perf_counter() - t0
        assert dash["never_modifies_production"] is True
        assert dash["execution_score"]["overall_execution_score"] is not None
        assert elapsed < 45
