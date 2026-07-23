"""Network / DNS incident tracker — production reliability observability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.institutional_trading.reliability.health import ProbeInputs
from app.domain.institutional_trading.reliability.models import IncidentSeverity
from app.domain.institutional_trading.reliability.network_incidents import (
    NetworkIncidentTracker,
    RecoveryStatus,
    is_dns_error,
    is_network_error,
)
from app.domain.institutional_trading.reliability.platform import (
    ReliabilityPlatform,
    reset_reliability_platform_for_tests,
)


@pytest.mark.unit
class TestNetworkClassification:
    def test_dns_getaddrinfo_detected(self) -> None:
        err = "[Errno 11001] getaddrinfo failed"
        assert is_dns_error(err, "ConnectError")
        assert is_network_error(err, "ConnectError")

    def test_single_recovered_dns_is_info(self) -> None:
        tracker = NetworkIncidentTracker()
        now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
        opened = tracker.observe_transport_failure(
            error="getaddrinfo failed",
            error_type="ConnectError",
            component="gateway",
            retry_count=1,
            now=now,
        )
        assert opened is not None
        assert opened.kind == "dns"
        recovered = tracker.mark_recovered(
            component="gateway",
            now=now + timedelta(seconds=2),
            detail="ok",
        )
        assert recovered is not None
        assert recovered.recovery_status == RecoveryStatus.RECOVERED
        assert recovered.severity is IncidentSeverity.INFO
        assert recovered.duration_ms >= 2000
        assert recovered.retry_count >= 1

    def test_repeated_failures_escalate(self) -> None:
        tracker = NetworkIncidentTracker()
        now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
        for i in range(4):
            tracker.observe_transport_failure(
                error="getaddrinfo failed",
                error_type="ConnectError",
                component="gateway",
                retry_count=i,
                now=now + timedelta(seconds=i * 10),
            )
            if i < 3:
                tracker.mark_recovered(
                    component="gateway",
                    now=now + timedelta(seconds=i * 10 + 1),
                )
        # 4th still open → CRITICAL cluster
        open_rows = [
            i
            for i in tracker.list_incidents()
            if i.recovery_status == RecoveryStatus.ONGOING
        ]
        assert open_rows
        assert open_rows[-1].severity is IncidentSeverity.CRITICAL

    def test_reconnect_always_logged(self) -> None:
        tracker = NetworkIncidentTracker()
        tracker.log_reconnect_attempt(
            component="gateway",
            attempt=1,
            detail="starting",
            success=None,
        )
        tracker.log_reconnect_attempt(
            component="gateway",
            attempt=1,
            detail="done",
            success=True,
            duration_ms=120.0,
        )
        logs = tracker.list_reconnect_logs()
        assert len(logs) == 2
        dash = tracker.dashboard()
        assert dash["reconnect_count"] == 2
        assert dash["average_reconnect_time_ms"] == 120.0


@pytest.mark.unit
class TestPlatformNetworkDashboard:
    def test_dashboard_includes_network(self) -> None:
        platform = reset_reliability_platform_for_tests()
        t0 = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
        platform.tick(ProbeInputs(gateway_available=True, mt5_connected=True), now=t0)
        platform.tick(
            ProbeInputs(gateway_available=False, mt5_connected=True),
            now=t0 + timedelta(seconds=30),
        )
        platform.tick(
            ProbeInputs(gateway_available=True, mt5_connected=True),
            now=t0 + timedelta(seconds=45),
        )
        dash = platform.operational_dashboard()
        assert "network" in dash
        assert "network_incidents" in dash
        assert "reconnect_log" in dash
        net = dash["network"]
        assert "gateway_uptime_pct" in net
        assert "dns_failures_24h" in net
        assert "reconnect_count" in net
        assert "average_reconnect_time_ms" in net
        assert "mt5_connection_uptime_pct" in net
        assert net["last_network_incident"] is not None

    def test_recovery_logs_reconnects(self) -> None:
        platform = reset_reliability_platform_for_tests()
        platform.recovery.gateway_reconnect_fn = lambda: True
        ev = platform.recovery.recover_gateway()
        assert ev.success is True
        logs = platform.network.list_reconnect_logs()
        assert len(logs) >= 2  # start + complete — never silent
