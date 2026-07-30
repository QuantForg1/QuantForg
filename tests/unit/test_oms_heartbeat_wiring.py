"""OMS heartbeat must follow gateway submit path — not Railway self-probe."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    _oms_submit_path_healthy,
)
from app.domain.institutional_trading.ai_scalping import continuous_operation as co_mod
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.continuous_operation import (
    ContinuousOperationController,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.reliability.health import ProbeInputs
from app.domain.institutional_trading.reliability.models import ComponentName
from app.domain.institutional_trading.reliability.platform import ReliabilityPlatform


@pytest.fixture(autouse=True)
def _reset_continuous_ops_singleton() -> None:
    co_mod._CTRL = None
    yield
    co_mod._CTRL = None


def test_oms_path_healthy_when_gateway_up_even_if_railway_self_probe_down() -> None:
    probes = ProbeInputs(
        gateway_available=True,
        mt5_connected=True,
        railway_api_up=False,
        cloudflare_tunnel_up=True,
        supabase_up=False,
    )
    assert _oms_submit_path_healthy(probes) is True


def test_oms_path_unhealthy_when_gateway_down() -> None:
    probes = ProbeInputs(
        gateway_available=False,
        mt5_connected=True,
        railway_api_up=True,
        cloudflare_tunnel_up=False,
        supabase_up=False,
    )
    assert _oms_submit_path_healthy(probes) is False


def test_continuous_ops_does_not_pause_oms_when_gateway_ok() -> None:
    ctrl = ContinuousOperationController(config=DEFAULT_AI_SCALPING_CONFIG)
    snap = ctrl.tick(
        gateway_ok=True,
        mt5_ok=True,
        oms_ok=True,  # submit path healthy
        feed_ok=True,
        broker_available=True,
        market_open=True,
        portfolio_risk_exceeded=False,
    )
    assert snap.pause["pause_new_entries"] is False
    assert "oms" in snap.heartbeats["beats"]


def test_tick_health_publishes_oms_when_railway_self_probe_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: railway_api_up=False must not starve OMS heartbeat."""
    plane = MagicMock()
    plane.mode = OpsExecutionMode.LIVE
    plane.daily_loss_exceeded = False

    probes = ProbeInputs(
        gateway_available=True,
        mt5_connected=True,
        railway_api_up=False,
        cloudflare_tunnel_up=True,
        supabase_up=False,
        gateway_latency_ms=12.0,
    )
    collector = MagicMock()
    collector.collect = MagicMock(return_value=probes)

    reliability = ReliabilityPlatform()
    runtime = InstitutionalIteRuntime(
        plane=plane,
        reliability=reliability,
        probes=collector,
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
        interval_seconds=60.0,
        mt5_adapter=MagicMock(),
    )

    # Avoid portfolio/market side effects in continuous ops tick
    monkeypatch.setattr(
        "app.application.services.market_closed_cooldown.is_market_closed_cooled",
        lambda _sym: False,
    )

    result = runtime.tick_health()
    assert reliability.heartbeats.last(ComponentName.OMS) is not None
    co = result.get("continuous_operation") or {}
    pause = (co.get("pause") or {}) if isinstance(co, dict) else {}
    reasons = [str(r) for r in (pause.get("reasons") or [])]
    assert not any("stale heartbeat:oms" in r for r in reasons)
    assert pause.get("pause_new_entries") is False


def test_heartbeat_timeout_aligned_above_scheduler_interval() -> None:
    plane = MagicMock()
    plane.mode = OpsExecutionMode.LIVE
    plane.daily_loss_exceeded = False
    probes = ProbeInputs(
        gateway_available=True,
        mt5_connected=True,
        railway_api_up=True,
        cloudflare_tunnel_up=True,
        supabase_up=True,
    )
    collector = MagicMock()
    collector.collect = MagicMock(return_value=probes)
    reliability = ReliabilityPlatform()
    runtime = InstitutionalIteRuntime(
        plane=plane,
        reliability=reliability,
        probes=collector,
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
        interval_seconds=60.0,
        mt5_adapter=MagicMock(),
    )
    runtime.tick_health()
    assert reliability.heartbeats.timeout_seconds >= 125.0
    from app.domain.institutional_trading.ai_scalping.continuous_operation import (
        get_continuous_operation_controller,
    )

    ctrl = get_continuous_operation_controller(DEFAULT_AI_SCALPING_CONFIG)
    assert ctrl.heartbeats.timeout_seconds >= 125.0
