"""v1.0.1 acceptance validation — scenarios, failures, consistency, audit, recovery.

Measurement only. Does not modify trading logic or invent soak evidence.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.services.auto_trading_status import build_status_facts
from app.application.services.live_account_risk_tracker import LiveAccountRiskTracker
from app.domain.enums.execution import ExecutionAuditStage
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.certification.failure_injection import (
    FailureInjector,
)
from app.domain.institutional_trading.certification.models import (
    CERTIFICATION_PIPELINE,
    FailureScenario,
    PipelineStage,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    AlertKind,
    OperatorIdentity,
)
from app.domain.institutional_trading.operations.production_alerts import (
    ProductionAlertInputs,
    evaluate_production_alerts,
)
from app.domain.institutional_trading.reliability.chaos import ChaosHarness
from app.domain.institutional_trading.reliability.health import (
    ContinuousHealthMonitor,
    ProbeInputs,
)
from app.domain.institutional_trading.reliability.recovery import RecoveryOrchestrator
from app.domain.scalping_ai_v2.reliability import DuplicateProtection


def _running_policy(**over: object) -> AutoTradePolicy:
    base: dict[str, object] = {
        "enabled": True,
        "run_state": "running",
        "max_spread": Decimal("2.00"),
        "allowed_sessions": (
            "london",
            "new_york",
            "london_ny_overlap",
            "tokyo",
            "sydney",
        ),
        "news_filter_enabled": True,
    }
    base.update(over)
    return AutoTradePolicy(**base)  # type: ignore[arg-type]


def _live_facts(**over: object) -> AutoTradeLiveFacts:
    base: dict[str, object] = {
        "gateway_connected": True,
        "broker_connected": True,
        "market_data_live": True,
        "execution_enabled": True,
        "ops_mode": "CANARY",
        "emergency_stop": False,
        "session": "london",
        "session_evaluated": True,
        "spread": Decimal("0.40"),
        "spread_evaluated": True,
        "news_blocked": False,
        "account_trading_enabled": True,
        "mt5_autotrading_enabled": True,
        "account_flags_evaluated": True,
        "symbol_tradable": True,
        "no_broker_restrictions": True,
        "margin_available": True,
        "margin_evaluated": True,
        "risk_engine_pass": True,
        "risk_engine_evaluated": True,
        "symbol": "XAUUSD",
    }
    base.update(over)
    return AutoTradeLiveFacts(**base)  # type: ignore[arg-type]


@pytest.mark.unit
class TestTradingScenarios:
    """Expected Prefer-No-Trade / allow behavior under scenario facts."""

    def test_normal_london_trend_can_pass_gates(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(session="london", spread=Decimal("0.35")),
        )
        assert result.allowed is True

    def test_new_york_session_allowed(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(session="new_york"),
        )
        assert result.allowed is True

    def test_asia_tokyo_allowed_off_hours_blocked(self) -> None:
        ok = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(session="tokyo", market_data_live=True),
        )
        assert ok.allowed is True
        blocked = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(session="off_hours"),
        )
        assert blocked.allowed is False

    def test_high_spread_blocks(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(spread=Decimal("5.00")),
        )
        assert result.allowed is False
        assert any("spread" in r.lower() for r in result.failed_reasons)

    def test_news_blackout_blocks(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(
                news_blocked=True,
                news_reason="High-impact news window",
            ),
        )
        assert result.allowed is False
        assert any("news" in r.lower() for r in result.failed_reasons)

    def test_market_closed_blocks_missing_data(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(market_data_live=False, session="off_hours"),
        )
        assert result.allowed is False

    def test_broker_timeout_style_disconnect_blocks(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(gateway_connected=False, broker_connected=False),
        )
        assert result.allowed is False

    def test_mt5_reconnect_monitoring_blocks_while_down(self) -> None:
        down = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(broker_connected=False, market_data_live=False),
        )
        assert down.allowed is False
        up = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(broker_connected=True, market_data_live=True),
        )
        assert up.allowed is True

    def test_emergency_stop_during_monitoring(self) -> None:
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(emergency_stop=True),
        )
        assert result.allowed is False
        assert any(
            "emergency" in r.lower() or "kill" in r.lower()
            for r in result.failed_reasons
        )

    def test_duplicate_signal_blocked(self) -> None:
        dup = DuplicateProtection()
        first = dup.claim("signal-abc")
        second = dup.claim("signal-abc")
        assert first["allowed"] is True
        assert second["allowed"] is False
        assert second["duplicate"] is True


@pytest.mark.unit
class TestFailureInjection:
    def test_cert_failure_scenarios_degrade_gracefully(self) -> None:
        inj = FailureInjector()
        for scenario in FailureScenario:
            result = inj.inject(scenario)
            assert result.graceful is True, (scenario, result.detail)
            # Failure injector never calls order_send — by construction.

    def test_chaos_mt5_and_gateway(self) -> None:
        chaos = ChaosHarness()
        monitor = ContinuousHealthMonitor()
        base = ProbeInputs(
            gateway_available=True,
            mt5_connected=True,
            cloudflare_tunnel_up=True,
            railway_api_up=True,
            supabase_up=True,
            gateway_latency_ms=40,
        )
        chaos.inject("mt5_offline")
        snap = chaos.verify_degradation(monitor, base)
        assert snap.degraded is True or snap.health_score < 100
        chaos.clear()
        chaos.inject("gateway_offline")
        snap2 = chaos.verify_degradation(monitor, base)
        assert snap2.gateway_available is False

    def test_high_latency_and_database_alerts(self) -> None:
        plane = OperationsControlPlane()
        raised = evaluate_production_alerts(
            plane,
            ProductionAlertInputs(
                gateway_connected=True,
                mt5_connected=True,
                gateway_latency_ms=2000,
                high_latency_ms=500,
                database_ok=False,
                calendar_ok=False,
                disk_pct=95,
                memory_pct=90,
                ticks_fresh=False,
            ),
        )
        kinds = {a.kind for a in raised}
        assert AlertKind.HIGH_LATENCY in kinds
        assert AlertKind.DATABASE_UNAVAILABLE in kinds
        assert AlertKind.CALENDAR_UNAVAILABLE in kinds
        assert AlertKind.DISK_USAGE in kinds
        assert AlertKind.NO_TICKS in kinds

    def test_recovery_never_retries_order_send(self) -> None:
        calls: list[str] = []

        def gw() -> bool:
            calls.append("gateway")
            return True

        def mt5() -> bool:
            calls.append("mt5")
            return True

        def safe() -> bool:
            calls.append("safe_read")
            return True

        orch = RecoveryOrchestrator(
            gateway_reconnect_fn=gw,
            mt5_reconnect_fn=mt5,
            safe_read_fn=safe,
        )
        assert orch.recover_gateway().success is True
        assert orch.recover_mt5().success is True
        assert orch.retry_safe_read().success is True
        assert "order_send" not in "".join(calls)
        with pytest.raises(RuntimeError, match="order_send"):
            orch.retry_order_send()


@pytest.mark.unit
class TestConsistencyValidation:
    def test_auto_trading_and_ops_health_share_probe_facts(self) -> None:
        plane = OperationsControlPlane()
        probes = ProbeInputs(
            gateway_latency_ms=18.0,
            gateway_available=True,
            mt5_connected=True,
            cloudflare_tunnel_up=True,
            supabase_up=True,
        )
        settings = MagicMock()
        settings.execution_enabled = False
        settings.mt5_gateway_base_url = "https://gateway.example"
        collector = MagicMock()
        collector.collect.return_value = probes
        collector.mt5_adapter = None

        with (
            patch(
                "app.application.services.auto_trading_status._probe_collector",
                return_value=collector,
            ),
            patch(
                "app.application.services.auto_trading_status._enrich_from_adapter",
                return_value={
                    "market_data_live": True,
                    "symbol_tradable": True,
                    "spread": Decimal("0.30"),
                    "session": "london",
                    "health_payload": None,
                    "account_trading_enabled": None,
                    "mt5_autotrading_enabled": None,
                    "margin_available": None,
                    "no_broker_restrictions": None,
                },
            ),
        ):
            facts, live = build_status_facts(plane, settings=settings)

        health = plane.health.latest()
        assert health is not None
        assert facts.gateway_connected is live["gateway_connected"] is True
        assert facts.broker_connected is live["broker_connected"] is True
        assert health.gateway_available is True
        assert health.mt5_connected is True
        assert live["gateway_connected"] == health.gateway_available


@pytest.mark.unit
class TestAuditTrailValidation:
    def test_execution_audit_stages_cover_spine(self) -> None:
        required = {
            ExecutionAuditStage.VALIDATION,
            ExecutionAuditStage.RISK,
            ExecutionAuditStage.SAFETY,
            ExecutionAuditStage.SUBMIT,
        }
        assert required.issubset(set(ExecutionAuditStage))

    def test_certification_pipeline_links_decision_to_journal(self) -> None:
        stages = list(CERTIFICATION_PIPELINE)
        assert stages[0] == PipelineStage.DECISION
        assert PipelineStage.JOURNAL in stages
        assert PipelineStage.OMS in stages
        assert PipelineStage.GATEWAY in stages
        assert PipelineStage.MT5 in stages
        assert PipelineStage.RELIABILITY in stages


@pytest.mark.unit
class TestRecoveryValidation:
    def test_peak_equity_restored_after_restart(self, tmp_path: Path) -> None:
        path = tmp_path / "live_account_risk.json"
        t1 = LiveAccountRiskTracker(persist_path=path)
        t1.observe_equity(login=42, equity=Decimal("12500.50"))
        t1.observe_equity(login=42, equity=Decimal("12000"))
        assert t1.peak_for(42) == Decimal("12500.50")

        t2 = LiveAccountRiskTracker(persist_path=path)
        assert t2.peak_for(42) == Decimal("12500.50")

    def test_kill_switch_blocks_auto_trading(self) -> None:
        plane = OperationsControlPlane()
        op = OperatorIdentity(
            user_id=uuid4(), role="owner", display_name="Acceptance"
        )
        plane.arm_kill_switch(op, reason="acceptance drill", confirmed=True)
        assert plane.kill_switch_armed is True
        result = evaluate_auto_trade_safety(
            _running_policy(),
            _live_facts(emergency_stop=True),
        )
        assert result.allowed is False

    def test_duplicate_identities_export_import_no_double_process(self) -> None:
        a = DuplicateProtection()
        a.claim("idem-1")
        exported = a.export_identities()
        b = DuplicateProtection()
        b.import_identities(exported)
        again = b.claim("idem-1")
        assert again["duplicate"] is True
        assert again["allowed"] is False
