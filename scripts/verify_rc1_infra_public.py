#!/usr/bin/env python3
"""Post-recovery public verifier for gateway + staging + production tips.

Writes sanitized JSON under docs/production/infra_recovery_evidence/.
Never prints tokens.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _probe(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(8000).decode("utf-8", "replace")
            try:
                body: object = json.loads(raw)
            except json.JSONDecodeError:
                body = raw[:500]
            return {
                "url": url,
                "http_status": int(resp.status),
                "ok": 200 <= int(resp.status) < 300,
                "body": body,
                "server": resp.headers.get("server"),
                "cf_ray": resp.headers.get("cf-ray"),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(800).decode("utf-8", "replace") if exc.fp else ""
        return {
            "url": url,
            "http_status": int(exc.code),
            "ok": False,
            "body": raw[:500],
            "error": "HTTPError",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "http_status": None,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = root / "docs" / "production" / "infra_recovery_evidence"
    out.mkdir(parents=True, exist_ok=True)
    urls = [
        "https://gateway.quantforg.com/health",
        "https://quantforg-production.up.railway.app/health",
        "https://quantforg-production.up.railway.app/api/v1/ite/ops/rc1-production-validation",
        "https://quantforg-staging.up.railway.app/health",
    ]
    report = {"collected_at": _now(), "probes": [_probe(u) for u in urls]}
    gw = report["probes"][0]
    report["gateway_http_200"] = bool(gw.get("ok") and gw.get("http_status") == 200)
    path = out / "post_recovery_public_verify.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(path), "gateway_http_200": report["gateway_http_200"]}, indent=2))
    return 0 if report["gateway_http_200"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
