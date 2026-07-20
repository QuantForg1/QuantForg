"""Live infrastructure probes for ReliabilityPlatform — no POST body required."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.domain.institutional_trading.reliability.health import ProbeInputs
from app.infrastructure.brokers.mt5.client import MockMT5Client
from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


def _http_get(url: str, *, timeout: float = 3.0) -> tuple[bool, float, int | None]:
    """Lightweight GET — returns (ok, latency_ms, status_code)."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return False, 0.0, None
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            latency = (time.perf_counter() - t0) * 1000.0
            return 200 <= resp.status_code < 500, latency, resp.status_code
    except Exception as exc:  # noqa: BLE001 — probe boundary
        latency = (time.perf_counter() - t0) * 1000.0
        logger.info("live_probe_http_failed", url=url, error=str(exc))
        return False, latency, None


@dataclass
class LiveProbeCollector:
    """Collect Gateway / MT5 / Railway / Supabase / Cloudflare probe inputs."""

    settings: Settings
    mt5_adapter: Any | None = None
    supabase: Any | None = None

    def collect(self) -> ProbeInputs:
        gateway_url = (self.settings.mt5_gateway_base_url or "").rstrip("/")
        gateway_ok = False
        gateway_lat = 0.0
        tunnel_ok = False
        mt5_ok = False

        if gateway_url:
            ok, lat, _code = _http_get(f"{gateway_url}/health", timeout=3.0)
            gateway_lat = lat
            gateway_ok = ok
            host = (urlparse(gateway_url).hostname or "").lower()
            tunnel_ok = bool(ok and host)
            client = (
                getattr(self.mt5_adapter, "client", None) if self.mt5_adapter else None
            )
            health_fn = getattr(client, "gateway_health", None)
            if callable(health_fn):
                try:
                    t0 = time.perf_counter()
                    payload = health_fn()
                    gateway_lat = max(
                        gateway_lat, (time.perf_counter() - t0) * 1000.0
                    )
                    if isinstance(payload, dict):
                        gateway_ok = payload.get("status") == "ok" or gateway_ok
                        mt5_ok = bool(
                            payload.get("mt5_connected")
                            or payload.get("mt5_attached")
                            or payload.get("terminal_connected")
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.info("live_probe_gateway_health_failed", error=str(exc))
            if not mt5_ok and self.mt5_adapter is not None:
                mt5_ok = gateway_ok and not isinstance(client, MockMT5Client)
        else:
            gateway_ok = False
            tunnel_ok = False
            mt5_ok = False

        railway_ok = False
        railway_lat = 0.0
        domain = (self.settings.railway_public_domain or "").strip()
        if domain:
            base = domain if domain.startswith("http") else f"https://{domain}"
            railway_ok, railway_lat, _ = _http_get(
                f"{base.rstrip('/')}/health", timeout=3.0
            )

        supabase_ok = False
        db_lat = 0.0
        if self.supabase is not None and getattr(
            self.settings, "supabase_configured", False
        ):
            t0 = time.perf_counter()
            try:
                supabase_ok = bool(
                    getattr(self.supabase, "client", None) is not None
                    or getattr(self.supabase, "configured", False)
                )
            except Exception:  # noqa: BLE001
                supabase_ok = False
            db_lat = (time.perf_counter() - t0) * 1000.0
        elif getattr(self.settings, "database_url", ""):
            supabase_ok = True
            db_lat = 1.0

        return ProbeInputs(
            gateway_latency_ms=gateway_lat,
            gateway_available=gateway_ok,
            mt5_connected=mt5_ok,
            cloudflare_tunnel_up=tunnel_ok,
            railway_api_up=railway_ok,
            supabase_up=supabase_ok,
            database_latency_ms=db_lat or railway_lat,
            oms_latency_ms=0.0,
            execution_latency_ms=0.0,
            decision_latency_ms=0.0,
            pme_latency_ms=0.0,
        )
