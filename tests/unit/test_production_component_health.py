"""Unit tests for production trading-component health derivation."""

from __future__ import annotations

import pytest

from app.application.services.production_component_health import (
    collect_trading_component_health,
    derive_ai_status,
    derive_oms_status,
    reset_trading_components_cache,
)
from app.domain.institutional_trading.reliability.health import ProbeInputs


def test_oms_healthy_when_live_path_ready() -> None:
    result = derive_oms_status(
        execution_enabled=True,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=False,
    )
    assert result.status == "HEALTHY"


def test_oms_not_ready_when_mock() -> None:
    result = derive_oms_status(
        execution_enabled=True,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=True,
    )
    assert result.status == "NOT_READY"
    assert "mt5_use_mock" in result.detail


def test_oms_disabled_when_execution_off() -> None:
    result = derive_oms_status(
        execution_enabled=False,
        gateway_available=True,
        mt5_connected=True,
        mt5_use_mock=False,
    )
    assert result.status == "DISABLED"


def test_ai_healthy_only_with_runtime() -> None:
    assert derive_ai_status(ite_runtime_present=True).status == "HEALTHY"
    missing = derive_ai_status(ite_runtime_present=False)
    assert missing.status == "NOT_READY"
    assert "ite_runtime" in missing.detail


def test_collect_skips_platform_probes_and_includes_timing() -> None:
    class _Settings:
        execution_enabled = True
        mt5_use_mock = False
        mt5_enabled = True

    probes = ProbeInputs(
        gateway_latency_ms=120.0,
        gateway_available=True,
        mt5_connected=True,
        cloudflare_tunnel_up=True,
        railway_api_up=False,
        supabase_up=False,
        database_latency_ms=0.0,
        oms_latency_ms=0.0,
        execution_latency_ms=0.0,
        decision_latency_ms=0.0,
        pme_latency_ms=0.0,
    )
    reset_trading_components_cache()
    payload = collect_trading_component_health(
        _Settings(),  # type: ignore[arg-type]
        probes=probes,
        ite_runtime_present=True,
        use_cache=False,
    )
    assert payload["statuses"]["gateway"] == "HEALTHY"
    assert payload["statuses"]["mt5"] == "CONNECTED"
    assert payload["statuses"]["oms"] == "HEALTHY"
    assert payload["timing"]["platform_probes"] is False
    assert payload["timing"]["cache_hit"] is False
    assert "gateway_ms" in payload["timing"]


def test_collect_cache_hit_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.application.services import production_component_health as mod

    class _Settings:
        execution_enabled = True
        mt5_use_mock = False
        mt5_enabled = True
        mt5_gateway_base_url = "https://gateway.example"
        railway_public_domain = "quantforg-production.up.railway.app"

    calls: list[dict[str, object]] = []

    def fake_collect(self, **kwargs):  # noqa: ANN001
        calls.append(kwargs)
        return ProbeInputs(
            gateway_latency_ms=50.0,
            gateway_available=True,
            mt5_connected=True,
            cloudflare_tunnel_up=True,
            railway_api_up=False,
            supabase_up=False,
            database_latency_ms=0.0,
            oms_latency_ms=0.0,
            execution_latency_ms=0.0,
            decision_latency_ms=0.0,
            pme_latency_ms=0.0,
        )

    monkeypatch.setattr(mod.LiveProbeCollector, "collect", fake_collect)
    reset_trading_components_cache()
    first = collect_trading_component_health(
        _Settings(),  # type: ignore[arg-type]
        ite_runtime_present=True,
    )
    second = collect_trading_component_health(
        _Settings(),  # type: ignore[arg-type]
        ite_runtime_present=True,
    )
    assert len(calls) == 1
    assert calls[0].get("include_platform_probes") is False
    assert first["timing"]["cache_hit"] is False
    assert second["timing"]["cache_hit"] is True


def test_live_probe_skips_railway_when_platform_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services import institutional_live_probes as probes_mod
    from app.application.services.institutional_live_probes import LiveProbeCollector

    class _Settings:
        mt5_gateway_base_url = "https://gateway.quantforg.com"
        railway_public_domain = "quantforg-production.up.railway.app"
        supabase_configured = False
        database_url = ""

    urls: list[str] = []

    def fake_http(url: str, *, timeout: float = 8.0):
        urls.append(url)
        return (
            True,
            40.0,
            200,
            {"status": "ok", "mt5": {"connected": True}},
            True,
        )

    monkeypatch.setattr(probes_mod, "_http_get_json", fake_http)
    probes_mod.reset_gateway_probe_cache()
    collector = LiveProbeCollector(settings=_Settings())  # type: ignore[arg-type]
    result = collector.collect(include_platform_probes=False)
    assert result.gateway_available is True
    assert result.mt5_connected is True
    assert result.railway_api_up is False
    assert len(urls) == 1
    assert urls[0].endswith("/health")
    assert "railway.app" not in urls[0]


def test_live_probe_runs_gateway_and_railway_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services import institutional_live_probes as probes_mod
    from app.application.services.institutional_live_probes import LiveProbeCollector

    class _Settings:
        mt5_gateway_base_url = "https://gateway.quantforg.com"
        railway_public_domain = "quantforg-production.up.railway.app"
        supabase_configured = False
        database_url = ""

    urls: list[str] = []

    def fake_http(url: str, *, timeout: float = 8.0):
        urls.append(url)
        if "railway" in url:
            return True, 5000.0, 200, {"status": "ok"}, False
        return (
            True,
            40.0,
            200,
            {"status": "ok", "mt5": {"connected": True}},
            True,
        )

    monkeypatch.setattr(probes_mod, "_http_get_json", fake_http)
    probes_mod.reset_gateway_probe_cache()
    collector = LiveProbeCollector(settings=_Settings())  # type: ignore[arg-type]
    result = collector.collect(include_platform_probes=True)
    assert result.gateway_available is True
    assert result.railway_api_up is True
    assert len(urls) == 2


def test_live_probe_cache_dedupes_duplicate_gateway_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services import institutional_live_probes as probes_mod
    from app.application.services.institutional_live_probes import LiveProbeCollector

    class _Settings:
        mt5_gateway_base_url = "https://gateway.quantforg.com"
        railway_public_domain = ""
        supabase_configured = False
        database_url = ""

    urls: list[str] = []

    def fake_http(url: str, *, timeout: float = 8.0):
        urls.append(url)
        return (
            True,
            40.0,
            200,
            {"status": "ok", "mt5": {"connected": True}},
            True,
        )

    monkeypatch.setattr(probes_mod, "_http_get_json", fake_http)
    probes_mod.reset_gateway_probe_cache()
    a = LiveProbeCollector(settings=_Settings())  # type: ignore[arg-type]
    b = LiveProbeCollector(settings=_Settings())  # type: ignore[arg-type]
    first = a.collect(include_platform_probes=False)
    second = b.collect(include_platform_probes=False)
    assert first.gateway_available is True
    assert second.gateway_available is True
    assert len(urls) == 1
    assert b.last_health_payload is not None

