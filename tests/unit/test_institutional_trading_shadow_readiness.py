"""Shadow production blocker resolution tests — no OMS / strategy changes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_live_probes import LiveProbeCollector
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.institutional_oms_manage_adapter import (
    RecordingOmsManagePort,
)
from app.application.services.institutional_ops_guards import (
    GuardedOmsManagePort,
    GuardedOmsSubmitPort,
)
from app.application.services.institutional_position_management import (
    InstitutionalPositionManagement,
)
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.kill_switch import KillSwitch
from app.domain.institutional_trading.execution.models import (
    ExecutionBridgeContext,
    ExecutionMode,
)
from app.domain.institutional_trading.operations.control_plane import (
    reset_control_plane_for_tests,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.reliability.models import TraceStage
from app.domain.institutional_trading.reliability.platform import (
    reset_reliability_platform_for_tests,
)
from tests.unit.test_institutional_trading_phase_c import (
    _account,
    _buy_decision,
    _snapshot,
)


@pytest.mark.unit
class TestSharedKillSwitch:
    def test_bridge_and_ops_share_kill(self) -> None:
        plane = reset_control_plane_for_tests()
        ks = KillSwitch().bind(plane)
        assert ks.enabled is False
        plane.kill_switch_armed = True
        assert ks.enabled is True
        ks.disarm()
        assert plane.kill_switch_armed is False

    def test_pme_reads_plane_kill(self) -> None:
        plane = reset_control_plane_for_tests()
        plane.kill_switch_armed = True
        manage = InstitutionalPositionManagement.create(
            RecordingOmsManagePort(), ops_plane=plane
        )
        from app.domain.institutional_trading.management.models import (
            ManagedPosition,
            PositionManageContext,
        )

        pos = ManagedPosition(
            ticket=1,
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("2300"),
            initial_volume=Decimal("0.1"),
            remaining_volume=Decimal("0.1"),
            initial_stop=Decimal("2290"),
            risk_distance=Decimal("10"),
            opened_at=datetime.now(UTC),
        )
        manage.register(pos)
        ctx = PositionManageContext(
            now=datetime.now(UTC),
            current_price=Decimal("2310"),
            atr=Decimal("5"),
            kill_switch_armed=False,  # stale — plane wins
        )
        result = manage.evaluate(1, ctx)
        assert result.action.value == "daily_shutdown"


@pytest.mark.unit
class TestGuardedPortsAndShadowTrace:
    def test_guarded_submit_blocks_in_shadow(self) -> None:
        plane = reset_control_plane_for_tests()
        assert plane.mode is OpsExecutionMode.SHADOW
        inner = RecordingOmsPort()
        guarded = GuardedOmsSubmitPort(inner=inner, plane=plane)
        from app.application.services.institutional_execution_engine import (
            parse_order_intent,
        )

        intent = parse_order_intent(
            symbol="XAUUSD",
            side="buy",
            order_type="market",
            volume="0.01",
        )
        result = guarded.submit_market(
            user_id=uuid4(),
            request_id="r1",
            intent=intent,
            connected=True,
            login=None,
        )
        assert result.outcome == "disabled"
        assert result.gateway_status == "not_called"
        assert len(inner.calls) == 0

    def test_shadow_bridge_auto_trace(self) -> None:
        plane = reset_control_plane_for_tests()
        rel = reset_reliability_platform_for_tests()
        oms = RecordingOmsPort()
        guarded = GuardedOmsSubmitPort(inner=oms, plane=plane)
        integ = InstitutionalExecutionIntegration.create(
            guarded, config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
        )
        integ.bridge.bind_ops(plane, reliability=rel)
        decision, snap, acct = _buy_decision()
        ctx = ExecutionBridgeContext(
            snapshot=snap,
            account=acct,
            expected_input_hash=decision.input_hash,
            now=decision.as_of,
            user_id=uuid4(),
            execution_enabled=False,
            risk_allowed=True,
        )
        result = integ.bridge.handle(decision, ctx)
        assert result.forwarded_to_oms is False
        assert len(oms.calls) == 0
        traces = rel.traces.list(limit=5)
        assert traces
        stages = [s.stage for s in traces[-1].spans]
        assert TraceStage.BRIDGE in stages
        assert TraceStage.JOURNAL in stages
        assert TraceStage.OMS in stages


@pytest.mark.unit
class TestShadowOrchestrator:
    def test_cycle_never_forwards_oms(self) -> None:
        plane = reset_control_plane_for_tests()
        rel = reset_reliability_platform_for_tests()
        inner = RecordingOmsPort()
        guarded_s = GuardedOmsSubmitPort(inner=inner, plane=plane)
        guarded_m = GuardedOmsManagePort(inner=RecordingOmsManagePort(), plane=plane)
        integ = InstitutionalExecutionIntegration.create(
            guarded_s, config=ExecutionBridgeConfig(mode=ExecutionMode.SHADOW)
        )
        integ.bridge.bind_ops(plane, reliability=rel)
        pme = InstitutionalPositionManagement.create(guarded_m, ops_plane=plane)

        class _Settings:
            mt5_gateway_base_url = ""
            railway_public_domain = "quantforg-production.up.railway.app"
            supabase_configured = False
            database_url = "postgresql://x"

        runtime = InstitutionalIteRuntime(
            plane=plane,
            reliability=rel,
            probes=LiveProbeCollector(settings=_Settings()),  # type: ignore[arg-type]
            guarded_submit=guarded_s,
            guarded_manage=guarded_m,
            execution=integ,
            position_management=pme,
        )
        snap = _snapshot()
        account = _account()
        cycle = runtime.run_shadow_cycle(snapshot=snap, account=account)
        assert cycle.ok
        assert cycle.forwarded_to_oms is False
        assert cycle.trace_id
        assert len(inner.calls) == 0
        assert cycle.decision_action is not None


@pytest.mark.unit
class TestLiveProbeGatewayHealthShape:
    """Readiness must parse real gateway /health, not invented flat keys."""

    def test_nested_mt5_connected(self) -> None:
        from app.application.services.institutional_live_probes import (
            mt5_connected_from_gateway_health,
        )

        payload = {
            "status": "ok",
            "service": "mt5-gateway",
            "mt5": {
                "connected": True,
                "session_mode": "attached",
                "latency_ms": 12.0,
            },
            "bridge_available": True,
        }
        assert mt5_connected_from_gateway_health(payload) is True

    def test_nested_mt5_disconnected(self) -> None:
        from app.application.services.institutional_live_probes import (
            mt5_connected_from_gateway_health,
        )

        payload = {
            "status": "ok",
            "mt5": {"connected": False, "session_mode": "none"},
        }
        assert mt5_connected_from_gateway_health(payload) is False

    def test_collector_uses_gateway_health_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.application.services import institutional_live_probes as probes_mod

        class _Settings:
            mt5_gateway_base_url = "https://abc.trycloudflare.com"
            railway_public_domain = ""
            supabase_configured = False
            database_url = ""

        class _GatewayClient:
            def gateway_health(self) -> dict:
                return {
                    "status": "ok",
                    "mt5": {"connected": True, "session_mode": "attached"},
                    "bridge_available": True,
                }

        class _Adapter:
            client = _GatewayClient()

        # Simulate Railway HTTP get failing (short timeout) while authenticated
        # gateway client still succeeds — probes must still pass.
        monkeypatch.setattr(
            probes_mod,
            "_http_get_json",
            lambda *a, **k: (False, 8000.0, None, None),
        )
        collector = LiveProbeCollector(
            settings=_Settings(),  # type: ignore[arg-type]
            mt5_adapter=_Adapter(),
        )
        result = collector.collect()
        assert result.gateway_available is True
        assert result.mt5_connected is True
        assert result.cloudflare_tunnel_up is True

    def test_collector_parses_public_health_json_without_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.application.services import institutional_live_probes as probes_mod

        class _Settings:
            mt5_gateway_base_url = "https://abc.trycloudflare.com"
            railway_public_domain = ""
            supabase_configured = False
            database_url = ""

        monkeypatch.setattr(
            probes_mod,
            "_http_get_json",
            lambda *a, **k: (
                True,
                40.0,
                200,
                {
                    "status": "ok",
                    "mt5": {"connected": True, "session_mode": "attached"},
                },
            ),
        )
        collector = LiveProbeCollector(settings=_Settings())  # type: ignore[arg-type]
        result = collector.collect()
        assert result.gateway_available is True
        assert result.mt5_connected is True
        assert result.cloudflare_tunnel_up is True
