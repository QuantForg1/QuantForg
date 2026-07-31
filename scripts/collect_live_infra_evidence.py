#!/usr/bin/env python3
"""Collect live infrastructure evidence using process Settings (no secret dumps).

Intended to run via: railway run python scripts/collect_live_infra_evidence.py
Writes sanitized JSON only — never prints tokens, DSNs, or passwords.
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
        # Never emit credential-like strings
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

    collector = LiveProbeCollector(settings=settings)
    probes = collector.collect()

    gateway_url = str(getattr(settings, "mt5_gateway_base_url", "") or "")
    gateway_configured = bool(gateway_url.strip())
    execution_enabled = bool(getattr(settings, "execution_enabled", False))
    mt5_enabled = bool(getattr(settings, "mt5_enabled", False))
    mt5_use_mock = bool(getattr(settings, "mt5_use_mock", True))

    # AI / OMS: outside API process use settings flags (never fabricate HEALTHY)
    ai_status = "SETTINGS_ONLY"
    oms_status = "ENABLED" if execution_enabled else "DISABLED"
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None:
            ai_status = "RUNTIME_PRESENT"
            oms_status = "RUNTIME_PRESENT"
    except Exception as exc:
        ai_status = f"ERROR:{type(exc).__name__}"

    # Direct gateway HTTP probe (sanitized)
    gateway_http: dict[str, Any] = {}
    try:
        import os

        import httpx

        base = (
            gateway_url.strip()
            or os.environ.get("MT5_GATEWAY_BASE_URL", "")
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

    # Public API health (no auth)
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
    health_probes = [
        http_get(f"{api}/health"),
        http_get(f"{api}/api/v1/health"),
        http_get(f"{api}/api/v1/health/status"),
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
            "status": "HEALTHY" if probes.gateway_available else "DOWN",
        },
        "mt5": {
            "enabled": mt5_enabled,
            "use_mock": mt5_use_mock,
            "connected": bool(probes.mt5_connected),
            "status": "CONNECTED" if probes.mt5_connected else "DISCONNECTED",
        },
        "oms": {
            "execution_enabled": execution_enabled,
            "latency_ms": probes.oms_latency_ms,
            "status": oms_status,
        },
        "ai": {
            "status": ai_status,
            "decision_latency_ms": probes.decision_latency_ms,
        },
        "platform": {
            "railway_api_up": bool(probes.railway_api_up),
            "supabase_up": bool(probes.supabase_up),
            "cloudflare_tunnel_up": bool(probes.cloudflare_tunnel_up),
            "database_latency_ms": probes.database_latency_ms,
        },
        "health_endpoints": health_probes,
        "gateway_http": gateway_http,
        "last_gateway_health_payload": _safe(collector.last_health_payload),
        "unknown_states": [],
    }

    # Record residual UNKNOWN / DOWN / incomplete for acceptance honesty
    for label, status in (
        ("gateway", evidence["gateway"]["status"]),
        ("mt5", evidence["mt5"]["status"]),
        ("oms", evidence["oms"]["status"]),
        ("ai", evidence["ai"]["status"]),
    ):
        bad = {
            "UNKNOWN",
            "DOWN",
            "DISCONNECTED",
            "RUNTIME_ABSENT",
            "SETTINGS_ONLY",
        }
        if status in bad or str(status).startswith("ERROR"):
            evidence["unknown_states"].append(
                {"component": label, "status": status}
            )

    path = out_dir / "authenticated_infra_probes.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    # Print summary only
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
