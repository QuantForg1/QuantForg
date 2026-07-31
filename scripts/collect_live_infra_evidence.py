#!/usr/bin/env python3
"""Collect live infrastructure evidence using process Settings (no secret dumps).

Intended to run via: railway run python scripts/collect_live_infra_evidence.py
Writes sanitized JSON only — never prints tokens, DSNs, or passwords.

OMS/AI statuses are derived from runtime evidence via
``production_component_health``. Prefer production
``/api/v1/health/trading-components`` for AI (ITE runtime lives in API process).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        lower = value.lower()
        if any(
            k in lower
            for k in ("password", "token", "secret", "postgres://", "postgresql://")
        ):
            return "[REDACTED]"
        if len(value) > 200:
            return value[:200] + "…"
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return _safe(value.to_dict())
        except Exception:
            return str(type(value).__name__)
    return str(type(value).__name__)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    out_dir = root / "docs" / "production" / "pre_live_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    from core.config.settings import get_settings

    settings = get_settings()

    from app.application.services.institutional_live_probes import LiveProbeCollector
    from app.application.services.production_component_health import (
        collect_trading_component_health,
    )

    collector = LiveProbeCollector(settings=settings)
    probes = collector.collect()
    local_trading = collect_trading_component_health(settings, probes=probes)

    gateway_url = str(getattr(settings, "mt5_gateway_base_url", "") or "")
    gateway_configured = bool(gateway_url.strip())
    execution_enabled = bool(getattr(settings, "execution_enabled", False))
    mt5_enabled = bool(getattr(settings, "mt5_enabled", False))
    mt5_use_mock = bool(getattr(settings, "mt5_use_mock", True))

    # Prefer production API component health for AI (runtime only in API process)
    import urllib.error
    import urllib.request

    def http_get(url: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = body[:300]
                return {
                    "url": url,
                    "http_status": int(resp.status),
                    "ok": True,
                    "body": _safe(parsed),
                }
        except urllib.error.HTTPError as exc:
            return {
                "url": url,
                "http_status": int(exc.code),
                "ok": False,
                "body": _safe(exc.read().decode("utf-8", errors="replace")[:300]),
            }
        except Exception as exc:
            return {
                "url": url,
                "http_status": None,
                "ok": False,
                "error": str(exc),
            }

    api = "https://quantforg-production.up.railway.app"
    trading_comp_probe = http_get(f"{api}/api/v1/health/trading-components")
    prod_trading = (
        trading_comp_probe.get("body")
        if trading_comp_probe.get("ok")
        and isinstance(trading_comp_probe.get("body"), dict)
        else None
    )

    # OMS: local derivation from live gateway/MT5 evidence is authoritative
    oms_status = str(local_trading["statuses"]["oms"])
    # AI: prefer production process status; else local (usually NOT_READY off-process)
    if prod_trading and isinstance(prod_trading.get("statuses"), dict):
        ai_status = str(prod_trading["statuses"].get("ai") or "UNKNOWN")
        ai_source = "production_trading_components"
        # Also prefer production OMS if present and HEALTHY
        prod_oms = str(prod_trading["statuses"].get("oms") or "")
        if prod_oms:
            oms_status = prod_oms
            oms_source = "production_trading_components"
        else:
            oms_source = "local_derivation"
        gateway_status = str(
            prod_trading["statuses"].get("gateway")
            or local_trading["statuses"]["gateway"]
        )
        mt5_status = str(
            prod_trading["statuses"].get("mt5") or local_trading["statuses"]["mt5"]
        )
    else:
        ai_status = str(local_trading["statuses"]["ai"])
        ai_source = "local_derivation_no_prod_endpoint"
        oms_source = "local_derivation"
        gateway_status = str(local_trading["statuses"]["gateway"])
        mt5_status = str(local_trading["statuses"]["mt5"])

    # Direct gateway HTTP probe (sanitized)
    gateway_http: dict[str, Any] = {}
    try:
        import os

        import httpx

        base = (
            gateway_url.strip() or os.environ.get("MT5_GATEWAY_BASE_URL", "")
        ).rstrip("/")
        token = os.environ.get("MT5_GATEWAY_CALLER_TOKEN", "")
        if base:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(f"{base}/health", headers=headers)
                gateway_http = {
                    "http_status": int(resp.status_code),
                    "ok": 200 <= resp.status_code < 300,
                    "content_type": resp.headers.get("content-type"),
                }
    except Exception as exc:
        gateway_http = {"error": type(exc).__name__}

    health_probes = [
        http_get(f"{api}/health"),
        http_get(f"{api}/api/v1/health"),
        http_get(f"{api}/api/v1/health/status"),
        trading_comp_probe,
        http_get(f"{api}/api/v1/ite/ops/rc1-production-validation"),
        http_get(f"{api}/api/v1/ite/ops/services-health"),
    ]

    evidence = {
        "collected_at": _now(),
        "source": "railway_run_live_probe_collector",
        "gateway": {
            "configured": gateway_configured,
            "available": bool(probes.gateway_available),
            "latency_ms": probes.gateway_latency_ms,
            "status": gateway_status,
        },
        "mt5": {
            "enabled": mt5_enabled,
            "use_mock": mt5_use_mock,
            "connected": bool(probes.mt5_connected),
            "status": mt5_status,
        },
        "oms": {
            "execution_enabled": execution_enabled,
            "latency_ms": probes.oms_latency_ms,
            "status": oms_status,
            "source": oms_source,
            "detail": local_trading["oms"].get("detail"),
        },
        "ai": {
            "status": ai_status,
            "source": ai_source,
            "decision_latency_ms": probes.decision_latency_ms,
            "detail": (
                (prod_trading or {}).get("ai", {}).get("detail")
                if prod_trading
                else local_trading["ai"].get("detail")
            ),
        },
        "platform": {
            "railway_api_up": bool(probes.railway_api_up),
            "supabase_up": bool(probes.supabase_up),
            "cloudflare_tunnel_up": bool(probes.cloudflare_tunnel_up),
            "database_latency_ms": probes.database_latency_ms,
        },
        "local_trading_components": _safe(local_trading),
        "production_trading_components": _safe(prod_trading),
        "health_endpoints": health_probes,
        "gateway_http": gateway_http,
        "last_gateway_health_payload": _safe(collector.last_health_payload),
        "unknown_states": [],
    }

    bad = {
        "UNKNOWN",
        "DOWN",
        "DISCONNECTED",
        "RUNTIME_ABSENT",
        "SETTINGS_ONLY",
        "NOT_READY",
        "DISABLED",
        "ENABLED",
    }
    for label, status in (
        ("gateway", evidence["gateway"]["status"]),
        ("mt5", evidence["mt5"]["status"]),
        ("oms", evidence["oms"]["status"]),
        ("ai", evidence["ai"]["status"]),
    ):
        if status in bad or str(status).startswith("ERROR"):
            evidence["unknown_states"].append({"component": label, "status": status})

    path = out_dir / "authenticated_infra_probes.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "written": str(path),
                "gateway": evidence["gateway"]["status"],
                "mt5": evidence["mt5"]["status"],
                "oms": evidence["oms"]["status"],
                "ai": evidence["ai"]["status"],
                "unknown_or_down": evidence["unknown_states"],
            },
            indent=2,
        )
    )
    return 0 if not evidence["unknown_states"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
