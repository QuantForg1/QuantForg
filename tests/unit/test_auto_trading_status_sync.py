"""Auto Trading status must use live gateway probes — not an empty ops HealthMonitor."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.services.auto_trading_status import (
    build_auto_trading_status,
    build_status_facts,
    resolve_primary_blocker,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.institutional_trading.reliability.health import ProbeInputs


def _op() -> OperatorIdentity:
    return OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Status Sync Tester",
    )


@pytest.mark.unit
class TestAutoTradingStatusLiveProbes:
    def test_gateway_connected_when_live_probe_up(self) -> None:
        plane = OperationsControlPlane()
        probes = ProbeInputs(
            gateway_latency_ms=12.0,
            gateway_available=True,
            mt5_connected=True,
            cloudflare_tunnel_up=True,
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
                    "account_trading_enabled": None,
                    "mt5_autotrading_enabled": None,
                    "symbol_tradable": True,
                    "no_broker_restrictions": None,
                    "market_data_live": True,
                    "margin_available": None,
                    "spread": Decimal("0.35"),
                    "session": None,
                    "health_payload": None,
                },
            ),
        ):
            facts, live = build_status_facts(plane, settings=settings)
            snap = build_auto_trading_status(plane, settings=settings)

        assert facts.gateway_connected is True
        assert facts.broker_connected is True
        assert facts.market_data_live is True
        assert live["gateway_connected"] is True
        assert plane.health.latest() is not None
        assert plane.health.latest().gateway_available is True
        assert "MT5 Gateway not connected" not in snap.safety.failed_reasons
        assert "Broker / MT5 not connected" not in snap.safety.failed_reasons
        assert "Risk Engine did not PASS" not in snap.safety.failed_reasons
        # Intentional defaults still reported accurately
        assert any("OFF" in r or "SHADOW" in r for r in snap.safety.failed_reasons)
        assert "connectivity" not in snap.reason_groups
        assert "operator" in snap.reason_groups
        assert snap.primary_blocker is not None
        assert "SHADOW" in snap.primary_blocker or "OFF" in snap.primary_blocker
        assert snap.blocking_category in {"operator", "configuration"}
        assert snap.execution_state["ops_mode"] == "SHADOW"
        assert snap.execution_state["execution_enabled"] is False
        assert snap.execution_state["gate_status"] == "Disabled"
        assert snap.execution_state["gateway_connected"] is True
        assert snap.execution_state["broker_connected"] is True

    def test_empty_ops_health_alone_was_the_bug(self) -> None:
        """Regression: empty HealthMonitor must not be the sole gateway truth."""
        plane = OperationsControlPlane()
        assert plane.health.latest() is None
        stale = AutoTradeLiveFacts(
            gateway_connected=bool(
                plane.health.latest() and plane.health.latest().gateway_available
            ),
            broker_connected=False,
            market_data_live=False,
            risk_engine_pass=False,
            ops_mode=plane.mode.value,
            execution_enabled=False,
        )
        bad = evaluate_auto_trade_safety(AutoTradePolicy(), stale)
        assert "MT5 Gateway not connected" in bad.failed_reasons


@pytest.mark.unit
class TestStatusSnapshotGates:
    def test_unevaluated_risk_does_not_block_status(self) -> None:
        result = evaluate_auto_trade_safety(
            AutoTradePolicy(enabled=True, run_state="running"),
            AutoTradeLiveFacts(
                gateway_connected=True,
                broker_connected=True,
                market_data_live=True,
                risk_engine_pass=True,
                risk_engine_evaluated=False,
                risk_engine_reasons=(
                    "Risk Engine not evaluated — no pending auto-trade decision",
                ),
                account_trading_enabled=True,
                mt5_autotrading_enabled=True,
                symbol_tradable=True,
                margin_available=True,
                no_broker_restrictions=True,
                session="london",
                session_evaluated=False,
                spread=None,
                spread_evaluated=False,
                ops_mode="LIVE",
                execution_enabled=True,
                status_snapshot=True,
            ),
        )
        assert "Risk Engine did not PASS" not in result.failed_reasons
        assert "Spread unavailable" not in " ".join(result.failed_reasons)

    def test_primary_blocker_prefers_ops_mode_over_connectivity(self) -> None:
        plane = OperationsControlPlane()
        plane.update_auto_trade_controls(
            _op(),
            enabled=True,
            run_state="running",
            reason="arm for blocker test",
        )
        facts = AutoTradeLiveFacts(
            gateway_connected=True,
            broker_connected=True,
            market_data_live=True,
            risk_engine_pass=True,
            risk_engine_evaluated=False,
            account_trading_enabled=True,
            mt5_autotrading_enabled=True,
            symbol_tradable=True,
            margin_available=True,
            no_broker_restrictions=True,
            session_evaluated=False,
            spread_evaluated=False,
            ops_mode="SHADOW",
            execution_enabled=False,
            status_snapshot=True,
        )
        safety = plane.evaluate_auto_trading(facts)
        primary, category = resolve_primary_blocker(safety)
        assert primary is not None
        assert "SHADOW" in primary
        assert category == "operator"
        assert safety.status == "Disabled"

    def test_operator_can_promote_mode(self) -> None:
        plane = OperationsControlPlane()
        assert plane.mode is OpsExecutionMode.SHADOW
        plane.transition_mode(
            _op(), OpsExecutionMode.CANARY, reason="test promote", confirmed=True
        )
        assert plane.mode is OpsExecutionMode.CANARY
