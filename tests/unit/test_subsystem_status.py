"""Subsystem status planes — Gateway / Research / Execution separation."""

from __future__ import annotations

import pytest

from app.domain.trading.subsystem_status import (
    build_subsystem_status,
    classify_gateway_reachability,
    classify_research_plane,
)

pytestmark = [pytest.mark.unit]


def test_gateway_not_configured() -> None:
    out = classify_gateway_reachability(gateway_url_configured=False)
    assert out["status"] == "NOT_CONFIGURED"


def test_gateway_timeout_class() -> None:
    out = classify_gateway_reachability(
        gateway_url_configured=True,
        gateway_online=False,
        last_error="Read timeout talking to trycloudflare",
    )
    assert out["status"] == "OFFLINE"
    assert "timeout" in out["label"].lower() or "Timeout" in out["label"]


def test_gateway_530_is_origin_unreachable_not_auth() -> None:
    out = classify_gateway_reachability(
        gateway_url_configured=True,
        gateway_online=False,
        last_error="CLOUDFLARE_ORIGIN_UNREACHABLE error code: 1033",
    )
    assert out["status"] == "OFFLINE"
    assert out["label"] == "CLOUDFLARE_ORIGIN_UNREACHABLE"
    assert "authentication" in out["detail"].lower()
    assert "token" not in out["detail"].lower()


def test_research_degraded_when_catalogue_unavailable_even_if_api_up() -> None:
    out = classify_research_plane(
        worker_status="RUNNING",
        catalogue_source="UNAVAILABLE",
        gateway_online=False,
    )
    assert out["status"] == "DEGRADED"
    assert out["degraded_reason"] == "broker_catalogue_unavailable"
    assert out["broker_catalogue_required"] is True


def test_research_running_with_live_broker_catalogue() -> None:
    out = classify_research_plane(
        worker_status="RUNNING",
        catalogue_source="LIVE_BROKER",
        gateway_online=True,
    )
    assert out["status"] == "RUNNING"


def test_build_subsystem_keeps_execution_blocked_when_flags_false() -> None:
    pack = build_subsystem_status(
        gateway_url_configured=True,
        gateway_online=False,
        worker_status="DEGRADED",
        catalogue_source="UNAVAILABLE",
        signal_count=0,
        execution_enabled=False,
        gateway_execution_enabled=False,
        orders_may_submit=False,
    )
    assert pack["gateway"]["status"] == "OFFLINE"
    assert pack["research"]["status"] == "DEGRADED"
    assert pack["execution"]["status"] == "BLOCKED"
    assert pack["authorizes_trade"] is False
    assert "EXECUTION_ENABLED=false" in pack["execution"]["detail"]
