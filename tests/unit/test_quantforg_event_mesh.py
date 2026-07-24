"""Unit tests — QuantForg Event Mesh."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_event_mesh.analytics import (
    build_timeline,
    derive_events,
    ordering_consistency_check,
    replay_consistency_check,
    replay_stream,
    route_subscribers,
    search_events,
)
from app.domain.quantforg_event_mesh.models import (
    EVENT_SOURCES,
    EVENT_TYPES,
    ISOLATION_FLAGS,
    EventType,
)
from app.domain.quantforg_event_mesh.platform import QuantForgEventMesh
from app.domain.quantforg_event_mesh.store import QemStore

pytestmark = pytest.mark.unit


def _ctx() -> dict:
    return {
        "sources": {
            "islm": {
                "registry": [
                    {
                        "strategy_id": "s1",
                        "name": "alpha",
                        "lifecycle_state": "Research",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-02T00:00:00+00:00",
                    }
                ],
                "approvals": [],
            },
            "replay": {
                "simulations": [
                    {
                        "simulation_id": "r1",
                        "mode": "historical_replay",
                        "completed_at": "2026-01-03T00:00:00+00:00",
                    }
                ],
                "jobs": [],
            },
            "simulation": {
                "simulations": [
                    {
                        "simulation_id": "sim1",
                        "mode": "Monte Carlo",
                        "completed_at": "2026-01-04T00:00:00+00:00",
                    }
                ]
            },
            "research_lab": {
                "experiments": [
                    {
                        "experiment_id": "e1",
                        "name": "gate",
                        "status": "completed",
                        "updated_at": "2026-01-05T00:00:00+00:00",
                    }
                ],
                "jobs": [],
            },
            "cvf": {
                "confidence": {"confidence": 72},
                "observed_at": "2026-01-06T00:00:00+00:00",
            },
            "qcs": {
                "level": {"level": "Ready"},
                "scores": {},
                "observed_at": "2026-01-07T00:00:00+00:00",
            },
            "irdp": {
                "releases": [
                    {
                        "release_id": "rel-1",
                        "version": "1.0.0",
                        "status": "approved",
                        "created_at": "2026-01-08T00:00:00+00:00",
                        "updated_at": "2026-01-09T00:00:00+00:00",
                    }
                ],
                "approvals": [],
                "rollbacks": [
                    {
                        "rollback_id": "rb1",
                        "release_id": "rel-0",
                        "created_at": "2026-01-10T00:00:00+00:00",
                    }
                ],
            },
            "qpm": {
                "metrics": {},
                "health": {},
                "observed_at": "2026-01-11T00:00:00+00:00",
            },
            "irap": {"alerts": [{"kind": "drawdown", "severity": "warning"}]},
            "eqs": {"alerts": [{"kind": "slippage", "severity": "warning"}]},
            "res": {"alerts": [{"kind": "latency", "severity": "warning"}]},
            "icp": {"alerts": [{"kind": "ops", "severity": "info"}]},
            "aoc": {"recommendations": []},
            "knowledge_graph": {"nodes": []},
            "trading_engine": {},
            "oms": {},
            "gateway": {},
        },
        "availability": {s: True for s in EVENT_SOURCES},
        "source_count": len(EVENT_SOURCES),
        "read_only": True,
    }


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["modifies_risk"] is False
        assert ISOLATION_FLAGS["approves_releases"] is False
        assert ISOLATION_FLAGS["event_distribution_read_only"] is True
        assert ISOLATION_FLAGS["events_immutable"] is True


class TestDeriveAndOrder:
    def test_event_types_and_ordering(self) -> None:
        events = derive_events(_ctx())
        assert events
        types = {e["event_type"] for e in events}
        assert EventType.STRATEGY_UPDATED.value in types
        assert EventType.REPLAY_COMPLETED.value in types
        assert EventType.SIMULATION_COMPLETED.value in types
        assert EventType.EXPERIMENT_COMPLETED.value in types
        assert EventType.VALIDATION_COMPLETED.value in types
        assert EventType.CERTIFICATION_COMPLETED.value in types
        assert EventType.RELEASE_CREATED.value in types
        assert EventType.RELEASE_APPROVED.value in types
        assert EventType.RELEASE_ROLLED_BACK.value in types
        assert EventType.PORTFOLIO_UPDATED.value in types
        assert EventType.RISK_ALERT.value in types
        assert EventType.EXECUTION_ALERT.value in types
        assert EventType.RELIABILITY_ALERT.value in types
        assert all(e["event_type"] in EVENT_TYPES for e in events)
        assert all(e.get("immutable") is True for e in events)
        assert ordering_consistency_check(events)["ok"] is True
        timeline = build_timeline(events)
        stamps = [str(t.get("timestamp") or "") for t in timeline]
        assert stamps == sorted(stamps)


class TestSearchRouteReplay:
    def test_search_route_replay(self) -> None:
        events = derive_events(_ctx())
        found = search_events(events, strategy_id="s1")
        assert found["total_matched"] >= 1
        found2 = search_events(events, release_id="rel-1")
        assert found2["total_matched"] >= 1
        found3 = search_events(events, category="alert")
        assert found3["total_matched"] >= 1
        routing = route_subscribers(events)
        assert routing["routes"]
        assert all(r.get("never_mutates_producer") for r in routing["routes"])
        replayed = replay_stream(events, limit=50)
        assert replayed["ordering"] == "ascending_timestamp"
        assert replay_consistency_check(events, replayed["stream"])["ok"] is True


class TestImmutability:
    def test_duplicate_rejected(self, tmp_path: Path) -> None:
        store = QemStore(path=tmp_path / "qem.json")
        ev = {
            "id": "fixed-id-1",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "producer": "islm",
            "category": "strategy",
            "severity": "info",
            "event_type": EventType.STRATEGY_CREATED.value,
            "correlation_id": "c1",
            "evidence_ids": [],
            "metadata": {},
        }
        assert store.append_event(ev) is not None
        assert store.append_event({**ev, "metadata": {"x": 1}}) is None
        assert len(store.list_events()) == 1


class TestPlatform:
    def test_dashboard(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        qem = QuantForgEventMesh(store=QemStore(path=tmp_path / "qem.json"))
        monkeypatch.setattr(
            "app.domain.quantforg_event_mesh.platform.gather_event_sources",
            _ctx,
        )
        t0 = time.perf_counter()
        pack = qem.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_modifies_strategies"] is True
        assert pack["never_modifies_risk"] is True
        assert pack["never_approves_releases"] is True
        assert pack["events_immutable"] is True
        assert pack["ordering_consistency"]["ok"] is True
        assert pack["replay_consistency"]["ok"] is True
        assert pack["sections"]["event_explorer"]
        assert pack["sections"]["live_event_stream"]
        assert pack["sections"]["timeline"]
        assert pack["sections"]["correlation_viewer"]
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
