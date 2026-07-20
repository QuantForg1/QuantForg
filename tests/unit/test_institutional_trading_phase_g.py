"""Phase G unit tests — reliability & observability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.institutional_trading.reliability.chaos import ChaosHarness
from app.domain.institutional_trading.reliability.health import (
    ContinuousHealthMonitor,
    ProbeInputs,
)
from app.domain.institutional_trading.reliability.models import (
    ComponentName,
    IncidentSeverity,
    TraceStage,
)
from app.domain.institutional_trading.reliability.platform import (
    ReliabilityPlatform,
    reset_reliability_platform_for_tests,
)
from app.domain.institutional_trading.reliability.recovery import RecoveryOrchestrator


@pytest.fixture()
def platform() -> ReliabilityPlatform:
    return reset_reliability_platform_for_tests()


@pytest.mark.unit
class TestHealthAndHeartbeat:
    def test_continuous_health_score(self) -> None:
        mon = ContinuousHealthMonitor()
        snap = mon.observe(
            ProbeInputs(
                gateway_available=False,
                mt5_connected=False,
                gateway_latency_ms=900,
            )
        )
        assert snap.health_score < 70
        assert snap.degraded is True

    def test_missing_heartbeat_creates_incident(
        self, platform: ReliabilityPlatform
    ) -> None:
        now = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
        platform.heartbeats.publish(ComponentName.GATEWAY, now=now)
        # Decision never published
        result = platform.tick(
            ProbeInputs(),
            now=now + timedelta(seconds=60),
            required_heartbeats=(ComponentName.GATEWAY, ComponentName.DECISION),
        )
        assert "decision" in result["missing_heartbeats"]
        assert platform.incidents.open_count() >= 1


@pytest.mark.unit
class TestTracing:
    def test_single_trace_id_all_stages(self, platform: ReliabilityPlatform) -> None:
        tid = platform.record_trade_path(decision_id="d-1")
        trace = platform.traces.get(tid)
        assert trace is not None
        stages = [s.stage for s in trace.spans]
        assert stages == [
            TraceStage.DECISION,
            TraceStage.ELIGIBILITY,
            TraceStage.BRIDGE,
            TraceStage.OMS,
            TraceStage.GATEWAY,
            TraceStage.MT5,
            TraceStage.PME,
            TraceStage.JOURNAL,
        ]
        assert all(s.trace_id == tid for s in [trace])
        assert trace.trace_id == tid


@pytest.mark.unit
class TestIncidentsAndEscalation:
    def test_escalation_rules(self, platform: ReliabilityPlatform) -> None:
        now = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
        inc = platform.incidents.open(
            severity=IncidentSeverity.CRITICAL,
            title="down",
            detail="x",
            source="test",
            now=now,
        )
        bumped = platform.incidents.apply_escalation(now=now + timedelta(minutes=6))
        assert any(b.id == inc.id for b in bumped)
        latest = platform.incidents.list()[-1]
        assert latest.escalation_level >= 2


@pytest.mark.unit
class TestRecovery:
    def test_reconnect_and_safe_read(self) -> None:
        calls = {"gw": 0, "mt5": 0, "read": 0}

        def gw() -> bool:
            calls["gw"] += 1
            return True

        def mt5() -> bool:
            calls["mt5"] += 1
            return True

        def read() -> bool:
            calls["read"] += 1
            return calls["read"] >= 2

        orch = RecoveryOrchestrator(
            gateway_reconnect_fn=gw,
            mt5_reconnect_fn=mt5,
            safe_read_fn=read,
            max_safe_read_retries=3,
        )
        assert orch.recover_gateway().success is True
        assert orch.recover_mt5().success is True
        assert orch.retry_safe_read().success is True
        assert calls["read"] == 2

    def test_never_retry_order_send(self) -> None:
        orch = RecoveryOrchestrator()
        with pytest.raises(RuntimeError, match="order_send"):
            orch.retry_order_send()


@pytest.mark.unit
class TestMetricsNotificationsTimeline:
    def test_live_metrics(self, platform: ReliabilityPlatform) -> None:
        platform.metrics.record_execution_latency(10)
        platform.metrics.record_gateway_latency(5)
        platform.metrics.record_fill()
        platform.metrics.record_reject()
        platform.metrics.record_oms_failure()
        platform.metrics.record_duplicate_prevented()
        platform.metrics.record_risk_reject()
        snap = platform.metrics.snapshot()
        assert snap["fills"] == 1
        assert snap["rejects"] == 1
        assert snap["fill_rate_pct"] == 50.0

    def test_notifications(self, platform: ReliabilityPlatform) -> None:
        results = platform.notifications.notify(
            channels=["slack", "telegram"],
            subject="test",
            body="hello",
        )
        assert results["slack"] is True
        assert results["telegram"] is True
        outbox = platform.notifications.outbox()
        assert len(outbox["slack"]) == 1

    def test_timeline_search_export(self, platform: ReliabilityPlatform) -> None:
        platform.tick(ProbeInputs())
        platform.record_trade_path()
        found = platform.timeline.search(q="trace", limit=50)
        assert found
        js = platform.timeline.export_json(found)
        assert "trace_id" in js
        csv = platform.timeline.export_csv(found)
        assert "timestamp" in csv


@pytest.mark.unit
class TestChaos:
    def test_chaos_degradation(self, platform: ReliabilityPlatform) -> None:
        platform.chaos.inject("gateway_offline")
        platform.chaos.inject("mt5_offline")
        platform.chaos.inject("high_latency")
        snap = platform.chaos.verify_degradation(platform.health, ProbeInputs())
        assert snap.degraded is True
        assert snap.gateway_available is False
        assert snap.mt5_connected is False
        assert snap.gateway_latency_ms >= 2000
        platform.chaos.clear()
        assert platform.chaos.active() == ()

    def test_database_unavailable(self) -> None:
        chaos = ChaosHarness()
        chaos.inject("database_unavailable")
        chaos.inject("tunnel_offline")
        probed = chaos.apply_to_probes(ProbeInputs())
        assert probed.supabase_up is False
        assert probed.cloudflare_tunnel_up is False


@pytest.mark.unit
class TestOperationalDashboard:
    def test_dashboard_payload(self, platform: ReliabilityPlatform) -> None:
        platform.heartbeats.publish(ComponentName.GATEWAY)
        platform.tick(ProbeInputs())
        dash = platform.operational_dashboard()
        assert "latency_series" in dash
        assert "active_incidents" in dash
        assert "recovery_events" in dash
        assert "metrics" in dash
