"""Unit tests — Institutional Observability Platform (monitoring only)."""

from __future__ import annotations

import pytest

from app.domain.institutional_observability.alerts import detect_alerts
from app.domain.institutional_observability.dependency import build_dependency_map
from app.domain.institutional_observability.errors import aggregate_errors
from app.domain.institutional_observability.health import probe_components
from app.domain.institutional_observability.latency import collect_latencies
from app.domain.institutional_observability.reports import build_observability_pack


@pytest.mark.unit
class TestInstitutionalObservability:
    def test_health_probes_with_ops_facts(self) -> None:
        health = probe_components(
            ops_facts={
                "gateway_connected": True,
                "broker_connected": False,
                "mt5_logged_in": True,
                "execution_enabled": False,
                "journal_ok": True,
            }
        )
        assert health["components"]["gateway"]["status"] == "healthy"
        assert health["components"]["broker"]["status"] == "down"
        assert health["components"]["api"]["status"] == "healthy"
        assert "counts" in health

    def test_latency_never_fabricates_unmeasured(self) -> None:
        lat = collect_latencies(samples={"gateway": 40.0})
        assert lat["latencies_ms"]["gateway"] == 40.0
        # decision not supplied and not auto-probed → null
        assert lat["latencies_ms"]["decision"] is None
        assert lat["note"]

    def test_error_aggregation(self) -> None:
        err = aggregate_errors(
            [
                {"severity": "warning", "action": "reconnect", "component": "gateway"},
                {"severity": "critical", "action": "timeout", "result": "failure"},
                {"severity": "error", "action": "retry", "component": "broker"},
            ]
        )
        assert err["totals"]["warnings"] >= 1
        assert err["totals"]["critical_events"] >= 1
        assert err["totals"]["timeouts"] >= 1
        assert err["totals"]["reconnects"] >= 1
        assert err["totals"]["retries"] >= 1
        assert err["totals"]["failures"] >= 1

    def test_dependency_map_chain(self) -> None:
        health = probe_components(ops_facts={"gateway_connected": True})
        dep = build_dependency_map(health)
        assert dep["chain"][0] == "frontend"
        assert dep["chain"][-1] == "reports"
        assert len(dep["edges"]) == len(dep["chain"]) - 1

    def test_alerts_gateway_broker(self) -> None:
        health = {
            "components": {
                "gateway": {"status": "down"},
                "broker": {"status": "down"},
                "journal_writer": {"status": "healthy"},
                "warehouse": {"status": "healthy"},
            }
        }
        alerts = detect_alerts(
            health=health,
            latencies={"high_latency": {"api": 300.0}},
            resources={"memory_percent": 95.0, "queue_depth": 150},
            errors={"totals": {"failures": 5}},
        )
        ids = {a["id"] for a in alerts["alerts"]}
        assert "gateway_disconnect" in ids
        assert "broker_disconnect" in ids
        assert "high_latency_api" in ids
        assert "repeated_failures" in ids
        assert "queue_growth" in ids
        assert "resource_exhaustion_memory" in ids

    def test_pack_observability_only(self) -> None:
        pack = build_observability_pack(
            ops_facts={
                "gateway_connected": True,
                "broker_connected": True,
                "mt5_logged_in": True,
                "execution_enabled": True,
                "journal_ok": True,
            },
            latency_samples={"api": 10.0, "gateway": 20.0},
            error_events=[],
        )
        assert pack["observability_only"] is True
        assert pack["never_modifies_trading_behaviour"] is True
        assert "daily_health_report" in pack["reports"]
        assert "weekly_reliability_report" in pack["reports"]
        assert "monthly_stability_report" in pack["reports"]
        assert "incident_report" in pack["reports"]
        assert isinstance(pack["recommendations"], list)
        assert pack["uptime"]["current_uptime_seconds"] >= 0

    def test_empty_errors_not_fabricated(self) -> None:
        err = aggregate_errors(None)
        assert err["status"] == "unavailable"
        assert err["sample_size"] == 0
