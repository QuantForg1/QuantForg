"""Live infrastructure probes for ReliabilityPlatform — no POST body required."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

from app.domain.institutional_trading.reliability.health import ProbeInputs
from app.infrastructure.brokers.mt5.client import MockMT5Client
from app.infrastructure.brokers.mt5.gateway_client import is_cloudflare_tunnel_url
from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)

# Cloudflare Quick Tunnels often exceed a 3s cold-start; keep probes honest.
_GATEWAY_PROBE_TIMEOUT_S = 8.0
# Trading-components only needs gateway /health (includes MT5). Keep tight so
# Mission Control never waits on an 8s ceiling when the tunnel is healthy (~1s).
TRADING_COMPONENTS_GATEWAY_TIMEOUT_S = 3.5
_RAILWAY_PROBE_TIMEOUT_S = 5.0
# Shared across trading-components + Auto Trading status so one Gateway RTT
# is reused instead of stacking sequential /health calls.
_GATEWAY_PROBE_CACHE_TTL_S = 5.0
_gateway_probe_cache_lock = threading.Lock()
_gateway_probe_cache: tuple[float, str, ProbeInputs, dict[str, Any] | None] | None = (
    None
)


def reset_gateway_probe_cache() -> None:
    """Test helper — drop the short Gateway /health process cache."""
    global _gateway_probe_cache
    with _gateway_probe_cache_lock:
        _gateway_probe_cache = None


def response_indicates_cloudflare(headers: Any) -> bool:
    """True when HTTP headers show the response came through Cloudflare."""
    if headers is None:
        return False
    try:
        items = headers.items() if hasattr(headers, "items") else []
        lower = {str(k).lower(): str(v) for k, v in items}
    except Exception:
        return False
    if lower.get("cf-ray"):
        return True
    server = (lower.get("server") or "").lower()
    return "cloudflare" in server


def _http_get_json(
    url: str, *, timeout: float = _GATEWAY_PROBE_TIMEOUT_S
) -> tuple[bool, float, int | None, dict[str, Any] | None, bool]:
    """Lightweight GET — returns (ok, latency_ms, status_code, json_or_none, via_cf)."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return False, 0.0, None, None, False
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            latency = (time.perf_counter() - t0) * 1000.0
            ok = 200 <= resp.status_code < 500
            via_cf = response_indicates_cloudflare(resp.headers)
            body: dict[str, Any] | None = None
            try:
                raw = resp.json()
                if isinstance(raw, dict):
                    body = raw
            except Exception:
                body = None
            return ok, latency, resp.status_code, body, via_cf
    except Exception as exc:
        latency = (time.perf_counter() - t0) * 1000.0
        logger.info("live_probe_http_failed", url=url, error=str(exc))
        return False, latency, None, None, False


def mt5_connected_from_gateway_health(payload: dict[str, Any]) -> bool:
    """True when gateway ``/health`` shows an active MT5 session.

    Matches the real gateway shape::

        {"status": "ok", "mt5": {"connected": true, "session_mode": "attached", ...}}

    Also accepts flattened keys used by older probes / Weltrade helpers.
    Explicit ``connected: false`` always wins over stale ``session_mode``.
    """
    nested = payload.get("mt5")
    if isinstance(nested, dict):
        if "connected" in nested or "mt5_connected" in nested:
            return bool(nested.get("connected") or nested.get("mt5_connected"))
        mode = str(nested.get("session_mode") or "").strip().lower()
        if mode in {"attached", "connected"}:
            return True

    flat_keys = (
        "mt5_connected",
        "mt5_attached",
        "terminal_connected",
        "connected",
    )
    if any(key in payload for key in flat_keys):
        return bool(
            payload.get("mt5_connected")
            or payload.get("mt5_attached")
            or payload.get("terminal_connected")
            or payload.get("connected")
        )

    mode = str(payload.get("session_mode") or "").strip().lower()
    return mode in {"attached", "connected"}


def gateway_available_from_health(
    payload: dict[str, Any] | None, *, http_ok: bool
) -> bool:
    """Gateway process reachable — ``status=ok`` or successful HTTP probe."""
    if isinstance(payload, dict) and str(payload.get("status") or "").lower() == "ok":
        return True
    return http_ok


@dataclass
class LiveProbeCollector:
    """Collect Gateway / MT5 / Railway / Supabase / Cloudflare probe inputs."""

    settings: Settings
    mt5_adapter: Any | None = None
    supabase: Any | None = None
    last_health_payload: dict[str, Any] | None = None

    def collect(
        self,
        *,
        include_platform_probes: bool = True,
        gateway_timeout_s: float | None = None,
    ) -> ProbeInputs:
        """Collect live probe inputs.

        ``include_platform_probes=False`` skips the Railway public-domain HTTP
        self-probe (often 3–5s and unused by trading-components). Gateway and
        Railway probes run concurrently when both are requested.
        """
        global _gateway_probe_cache
        gateway_timeout = (
            float(gateway_timeout_s)
            if gateway_timeout_s is not None
            else _GATEWAY_PROBE_TIMEOUT_S
        )
        gateway_url = (self.settings.mt5_gateway_base_url or "").rstrip("/")
        domain = (self.settings.railway_public_domain or "").strip()
        want_railway = bool(include_platform_probes and domain)
        cache_key = f"{gateway_url}|platform={int(include_platform_probes)}"

        if not include_platform_probes and gateway_url:
            with _gateway_probe_cache_lock:
                cached = _gateway_probe_cache
            if (
                cached is not None
                and cached[1] == cache_key
                and (time.monotonic() - cached[0]) <= _GATEWAY_PROBE_CACHE_TTL_S
            ):
                self.last_health_payload = (
                    dict(cached[3]) if isinstance(cached[3], dict) else None
                )
                return replace(cached[2])

        gateway_result: tuple[
            bool, float, int | None, dict[str, Any] | None, bool
        ] | None = None
        railway_result: tuple[
            bool, float, int | None, dict[str, Any] | None, bool
        ] | None = None

        def _probe_gateway() -> tuple[
            bool, float, int | None, dict[str, Any] | None, bool
        ]:
            if not gateway_url:
                return False, 0.0, None, None, False
            return _http_get_json(
                f"{gateway_url}/health", timeout=gateway_timeout
            )

        def _probe_railway() -> tuple[
            bool, float, int | None, dict[str, Any] | None, bool
        ]:
            base = domain if domain.startswith("http") else f"https://{domain}"
            return _http_get_json(
                f"{base.rstrip('/')}/health", timeout=_RAILWAY_PROBE_TIMEOUT_S
            )

        if gateway_url and want_railway:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_gw = pool.submit(_probe_gateway)
                fut_rw = pool.submit(_probe_railway)
                gateway_result = fut_gw.result()
                railway_result = fut_rw.result()
        elif gateway_url:
            gateway_result = _probe_gateway()
        elif want_railway:
            railway_result = _probe_railway()

        gateway_ok = False
        gateway_lat = 0.0
        tunnel_ok = False
        mt5_ok = False
        health_payload: dict[str, Any] | None = None
        via_cf = False

        if gateway_result is not None:
            ok, lat, _code, body, via_cf = gateway_result
            gateway_lat = lat
            if body is not None:
                health_payload = body
            gateway_ok = gateway_available_from_health(body, http_ok=ok)

            client = (
                getattr(self.mt5_adapter, "client", None) if self.mt5_adapter else None
            )
            health_fn = getattr(client, "gateway_health", None)
            # Prefer public /health body when present — avoid a second slow RTT.
            if callable(health_fn) and health_payload is None:
                try:
                    t0 = time.perf_counter()
                    payload = health_fn()
                    gateway_lat = max(gateway_lat, (time.perf_counter() - t0) * 1000.0)
                    if isinstance(payload, dict):
                        health_payload = payload
                        gateway_ok = gateway_available_from_health(
                            payload, http_ok=gateway_ok
                        )
                except Exception as exc:
                    logger.info("live_probe_gateway_health_failed", error=str(exc))

            # Persist for Auto Trading enrich — public /health already has
            # terminal_trade_allowed / mt5_autotrading_enabled without auth.
            self.last_health_payload = (
                dict(health_payload) if isinstance(health_payload, dict) else None
            )

            if health_payload is not None:
                mt5_ok = mt5_connected_from_gateway_health(health_payload)

            # If the gateway process is up via GatewayMT5Client but /health omitted
            # MT5 fields, treat a non-mock client as attached only when gateway_ok.
            # Prefer explicit health — do not invent MT5 up without evidence
            # when health payload is present but says disconnected.
            if (
                not mt5_ok
                and self.mt5_adapter is not None
                and gateway_ok
                and client is not None
                and not isinstance(client, MockMT5Client)
                and health_payload is None
            ):
                mt5_ok = True

            # Cloudflare: known tunnel URL markers, or CF response headers
            # (custom hostnames like gateway.quantforg.com). Never "any host".
            host = (urlparse(gateway_url).hostname or "").lower()
            if gateway_ok and host:
                tunnel_ok = is_cloudflare_tunnel_url(gateway_url) or via_cf
        else:
            gateway_ok = False
            tunnel_ok = False
            mt5_ok = False
            self.last_health_payload = None

        railway_ok = False
        railway_lat = 0.0
        if railway_result is not None:
            railway_ok, railway_lat, _, _, _ = railway_result

        supabase_ok = False
        db_lat = 0.0
        if include_platform_probes:
            if self.supabase is not None and getattr(
                self.settings, "supabase_configured", False
            ):
                t0 = time.perf_counter()
                try:
                    supabase_ok = bool(
                        getattr(self.supabase, "client", None) is not None
                        or getattr(self.supabase, "configured", False)
                    )
                except Exception:
                    supabase_ok = False
                db_lat = (time.perf_counter() - t0) * 1000.0
            elif getattr(self.settings, "database_url", ""):
                supabase_ok = True
                db_lat = 1.0

        probes = ProbeInputs(
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
        if not include_platform_probes and gateway_url:
            payload_copy = (
                dict(self.last_health_payload)
                if isinstance(self.last_health_payload, dict)
                else None
            )
            with _gateway_probe_cache_lock:
                _gateway_probe_cache = (
                    time.monotonic(),
                    cache_key,
                    replace(probes),
                    payload_copy,
                )
        return probes
