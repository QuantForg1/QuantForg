#!/usr/bin/env python3
"""Production hardening performance report — live API only (no mock market data).

Usage:
  E2E_EMAIL=... E2E_PASSWORD=... python scripts/perf_hardening_report.py

Optional:
  QF_API_BASE=https://…/api/v1
  QF_PERF_OUT=/tmp/qf_perf_report.json
"""

from __future__ import annotations

import json
import os
import resource
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

BASE = os.environ.get(
    "QF_API_BASE", "https://quantforg-production.up.railway.app/api/v1"
)
EMAIL = os.environ["E2E_EMAIL"]
PASSWORD = os.environ["E2E_PASSWORD"]
OUT = Path(os.environ.get("QF_PERF_OUT", "/tmp/qf_perf_hardening_report.json"))
TIMEOUT = httpx.Timeout(45.0, connect=20.0)


def _rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports bytes; Linux reports kilobytes.
    rss = float(usage.ru_maxrss)
    if rss > 10_000_000:  # likely bytes (macOS)
        return round(rss / (1024 * 1024), 2)
    return round(rss / 1024, 2)


def _login(client: httpx.Client) -> str:
    last: Exception | None = None
    for attempt in range(4):
        try:
            login = client.post(
                f"{BASE}/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
            )
            login.raise_for_status()
            token = login.json().get("access_token") or login.json().get("access")
            if not token:
                raise RuntimeError(f"login missing token: {login.text[:200]}")
            return str(token)
        except (httpx.HTTPError, RuntimeError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"login failed after retries: {last}")


def main() -> int:
    report: dict[str, Any] = {
        "base": BASE,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "client_rss_mb_start": _rss_mb(),
        "endpoints": {},
        "load": {},
        "recovery": {},
        "notes": [],
    }

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        targets: list[tuple[str, str, dict[str, Any] | None]] = [
            ("GET", "/mt5/status", None),
            ("GET", "/mt5/account", None),
            ("GET", "/mt5/symbols?limit=100&offset=0&include_quotes=false", None),
            ("GET", "/mt5/symbols?q=EUR&limit=50&include_quotes=false", None),
            ("GET", "/intelligence/market-context?market_code=FX", None),
            ("GET", "/intelligence/dashboard?market_code=FX", None),
            ("GET", "/portfolio", None),
            ("GET", "/weltrade/health", None),
        ]

        for method, path, body in targets:
            samples: list[float] = []
            last_status = 0
            last_bytes = 0
            last_payload: Any = None
            errors: list[str] = []
            for _ in range(3):
                t0 = time.perf_counter()
                try:
                    resp = client.request(
                        method,
                        f"{BASE}{path}",
                        headers=headers,
                        json=body,
                    )
                    elapsed = (time.perf_counter() - t0) * 1000
                    samples.append(elapsed)
                    last_status = resp.status_code
                    last_bytes = len(resp.content)
                    with __import__("contextlib").suppress(Exception):
                        last_payload = resp.json()
                except httpx.HTTPError as exc:
                    elapsed = (time.perf_counter() - t0) * 1000
                    samples.append(elapsed)
                    errors.append(f"{type(exc).__name__}: {exc}"[:160])
            entry: dict[str, Any] = {
                "status": last_status or None,
                "bytes": last_bytes,
                "errors": errors[:3],
            }
            if samples:
                entry["p50_ms"] = round(statistics.median(samples), 2)
                entry["p95_ms"] = round(
                    sorted(samples)[max(0, int(len(samples) * 0.95) - 1)], 2
                )
                entry["avg_ms"] = round(statistics.mean(samples), 2)
                entry["samples_ms"] = [round(s, 2) for s in samples]
            if path.startswith("/mt5/symbols") and isinstance(last_payload, dict):
                entry["total"] = last_payload.get("total")
                entry["items"] = len(last_payload.get("items") or [])
                entry["has_more"] = last_payload.get("has_more")
            report["endpoints"][path] = entry
        # Dashboard cache hit ratio proxy: back-to-back calls.
        dash_latencies: list[float] = []
        for _ in range(4):
            t0 = time.perf_counter()
            try:
                r = client.get(
                    f"{BASE}/intelligence/dashboard?market_code=FX",
                    headers=headers,
                )
                dash_latencies.append((time.perf_counter() - t0) * 1000)
                _ = r.status_code
            except httpx.HTTPError as exc:
                dash_latencies.append((time.perf_counter() - t0) * 1000)
                report["notes"].append(f"dashboard burst error: {exc}"[:160])
        report["load"]["dashboard_burst_ms"] = [round(x, 2) for x in dash_latencies]
        if len(dash_latencies) >= 2:
            report["load"]["dashboard_cache_speedup"] = round(
                dash_latencies[0] / max(dash_latencies[1], 1.0), 2
            )

        # Concurrent-ish sequential storm to estimate request rate.
        storm_n = 18
        t0 = time.perf_counter()
        ok = 0
        fail = 0
        for i in range(storm_n):
            path = "/mt5/status" if i % 2 == 0 else "/portfolio"
            try:
                r = client.get(f"{BASE}{path}", headers=headers)
                if r.status_code < 500:
                    ok += 1
                else:
                    fail += 1
            except httpx.HTTPError:
                fail += 1
        storm_s = max(time.perf_counter() - t0, 0.001)
        report["load"]["storm"] = {
            "requests": storm_n,
            "ok": ok,
            "fail": fail,
            "elapsed_s": round(storm_s, 3),
            "client_req_per_min": round((storm_n / storm_s) * 60, 1),
        }

        # Recovery: refresh + reconnect (attach) without disconnecting the live terminal.
        for name, path in (
            ("refresh", "/mt5/refresh"),
            ("reconnect", "/mt5/reconnect"),
            ("weltrade_refresh", "/weltrade/refresh"),
        ):
            t0 = time.perf_counter()
            try:
                r = client.post(f"{BASE}{path}", headers=headers, json={})
                report["recovery"][name] = {
                    "status": r.status_code,
                    "ms": round((time.perf_counter() - t0) * 1000, 2),
                    "body_preview": (r.text or "")[:240],
                }
            except httpx.HTTPError as exc:
                report["recovery"][name] = {
                    "status": None,
                    "error": str(exc),
                    "ms": round((time.perf_counter() - t0) * 1000, 2),
                }

        # Ops metrics if permitted.
        try:
            r = client.get(f"{BASE}/ops/metrics", headers=headers)
            if r.status_code == 200:
                payload = r.json()
                report["ops_metrics"] = {
                    "gateway": (payload.get("gateway") if isinstance(payload, dict) else None),
                    "intelligence_dashboard_cache": (
                        payload.get("intelligence_dashboard_cache")
                        if isinstance(payload, dict)
                        else None
                    ),
                    "keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                }
            else:
                report["notes"].append(f"ops/metrics HTTP {r.status_code} (role limited)")
        except httpx.HTTPError as exc:
            report["notes"].append(f"ops/metrics skipped: {exc}")

        report["client_rss_mb_end"] = _rss_mb()
        report["cpu_user_s"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_utime, 3)
        report["cpu_system_s"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_stime, 3)
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["notes"].append(
            "MT5 requests/min on the API process are exposed via gateway metrics "
            "in /ops/metrics (admin) and weltrade diagnostics.gateway_metrics."
        )
        report["notes"].append(
            "WebSocket event throughput: desk uses React Query polling channels; "
            "no separate WS broker stream in this deployment path."
        )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
