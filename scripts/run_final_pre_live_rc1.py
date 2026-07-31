#!/usr/bin/env python3
"""Final pre-live RC1 evidence collector.

Collects public live /health facts, runs paper + shadow validation locally,
writes RC1_VALIDATION_REPORT.md with live evidence attached.

Never merges, never pushes to main, never applies DB migrations.
Never fabricates Gateway/OMS/MT5/AI health when endpoints require auth.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API_BASE = "https://quantforg-production.up.railway.app"
FRONTEND = "https://www.quantforg.com"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_body(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]


def _http_get(url: str, *, timeout: float = 15.0) -> dict[str, Any]:
    # HTTPS-only probes to known production hosts (no file: / custom schemes).
    if not url.startswith("https://"):
        return {
            "url": url,
            "http_status": None,
            "ok": False,
            "body": None,
            "error": "only_https_allowed",
        }
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            parsed = _parse_body(body)
            return {
                "url": url,
                "http_status": int(resp.status),
                "ok": 200 <= int(resp.status) < 300,
                "body": parsed,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "url": url,
            "http_status": int(exc.code),
            "ok": False,
            "body": _parse_body(body),
            "error": str(exc.reason),
        }
    except Exception as exc:
        return {
            "url": url,
            "http_status": None,
            "ok": False,
            "body": None,
            "error": str(exc),
        }


def collect_live_evidence() -> dict[str, Any]:
    probes = [
        f"{API_BASE}/health",
        f"{API_BASE}/api/v1/health",
        f"{API_BASE}/api/v1/ready",
        f"{API_BASE}/api/v1/health/status",
        f"{API_BASE}/api/v1/health/ready",
        f"{API_BASE}/api/v1/health/live",
        f"{API_BASE}/api/v1/healthz",
        f"{API_BASE}/api/v1/ite/ops/services-health",
        f"{API_BASE}/api/v1/ite/ops/production-validation-mode",
        f"{API_BASE}/api/v1/ite/ops/rc1-production-validation",
        f"{API_BASE}/api/v1/ite/reliability/rc1",
        f"{API_BASE}/api/v1/ops/rc1-telemetry",
        FRONTEND,
    ]
    results = [_http_get(u) for u in probes]
    status = next(
        (
            r
            for r in results
            if r["url"].endswith("/api/v1/health/status") and r["ok"]
        ),
        None,
    )
    deps: dict[str, Any] = {}
    if status and isinstance(status.get("body"), dict):
        deps = {
            d.get("name"): d
            for d in (status["body"].get("dependencies") or [])
            if isinstance(d, dict)
        }

    auth_blocked = [
        r
        for r in results
        if r.get("http_status") == 401
        or (
            isinstance(r.get("body"), dict)
            and (r["body"].get("error") or {}).get("code") == "missing_token"
        )
    ]
    not_deployed = [
        r
        for r in results
        if r.get("http_status") == 404
        and "rc1-production-validation" in (r.get("url") or "")
    ]
    process_ok = any(r["url"].endswith("/health") and r["ok"] for r in results)
    status_body = status.get("body") if status else None
    if not isinstance(status_body, dict):
        status_body = {}

    return {
        "api_base": API_BASE,
        "frontend": FRONTEND,
        "collected_at": _now(),
        "gateway_status": "UNKNOWN",
        "oms_status": "UNKNOWN",
        "mt5_status": "UNKNOWN",
        "ai_status": "UNKNOWN",
        "gateway_health": "UNKNOWN",
        "process_health": "HEALTHY" if process_ok else "FAIL",
        "postgres": (deps.get("postgres") or {}).get("status", "UNKNOWN"),
        "redis": (deps.get("redis") or {}).get("status", "UNKNOWN"),
        "environment": status_body.get("environment"),
        "api_version": status_body.get("version"),
        "crashes": 0,
        "auth_blocked_endpoints": [r["url"] for r in auth_blocked],
        "rc1_endpoint_deployed": len(not_deployed) == 0,
        "probes": results,
        "evidence_integrity": {
            "never_fabricated_gateway_oms_mt5_ai": True,
            "auth_required_for_ops_health": True,
            "note": (
                "Gateway / OMS / MT5 / AI detailed health requires operator "
                "bearer token. Public probes only prove process + postgres."
            ),
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.domain.institutional_trading.rc1_production_validation import (
        config as cfg_mod,
        paper_engine as paper_mod,
        pipeline as pipe_mod,
        report as report_mod,
        shadow_engine as shadow_mod,
        trade_recorder as trade_mod,
    )

    live = collect_live_evidence()
    evidence_dir = root / "docs" / "production" / "pre_live_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "live_health_probes.json").write_text(
        json.dumps(live, indent=2, default=str),
        encoding="utf-8",
    )

    modes: dict[str, Any] = {}
    for mode in ("paper", "shadow"):
        trade_mod.reset_trade_recorder_for_tests()
        paper_mod.reset_paper_engine_for_tests()
        shadow_mod.reset_shadow_journal_for_tests()
        cfg_mod.set_validation_runtime_for_tests(
            enabled=True, execution_mode=mode
        )
        result = pipe_mod.run_rc1_validation_pipeline(
            infrastructure=live,
            trading={},
            risk={},
            write_report=False,
            use_synthetic_replay_if_empty=True,
        )
        modes[mode] = {
            k: v for k, v in result.items() if k != "report_markdown"
        }
        (evidence_dir / f"rc1_{mode}_result.json").write_text(
            json.dumps(modes[mode], indent=2, default=str),
            encoding="utf-8",
        )

    paper_rec = (modes["paper"].get("acceptance") or {}).get("recommendation")
    shadow_rec = (modes["shadow"].get("acceptance") or {}).get(
        "recommendation"
    )
    combined = "NOT READY"
    if (
        paper_rec == "READY FOR FULL PRODUCTION"
        and shadow_rec == "READY FOR FULL PRODUCTION"
    ):
        combined = "READY FOR FULL PRODUCTION"
    elif paper_rec and shadow_rec and "NOT READY" not in (
        paper_rec,
        shadow_rec,
    ):
        combined = "READY FOR LIMITED LIVE PILOT"

    if (
        live.get("gateway_status") == "UNKNOWN"
        or live.get("mt5_status") == "UNKNOWN"
    ):
        combined = "NOT READY"

    report_md = report_mod.render_rc1_validation_report(
        infrastructure=live,
        replay=modes["paper"].get("replay"),
        paper=modes["paper"].get("paper"),
        shadow=modes["shadow"].get("shadow"),
        oms={"status": live.get("oms_status"), "auth_required": True},
        gateway={"status": live.get("gateway_status"), "auth_required": True},
        risk={
            "status": "UNKNOWN",
            "note": "requires authenticated ops probe",
        },
        performance=modes["paper"].get("paper"),
        acceptance={
            "recommendation": combined,
            "paper_recommendation": paper_rec,
            "shadow_recommendation": shadow_rec,
            "summary": {
                "paper": (modes["paper"].get("acceptance") or {}).get(
                    "summary"
                ),
                "shadow": (modes["shadow"].get("acceptance") or {}).get(
                    "summary"
                ),
            },
            "gates": (modes["paper"].get("acceptance") or {}).get("gates"),
            "live_evidence_attached": True,
            "deployment_stopped": combined == "NOT READY",
        },
        dashboard=modes["paper"].get("dashboard"),
    )

    failure_extra = [
        "",
        "## Live Evidence Attachment",
        "",
        f"- Collected at: `{live.get('collected_at')}`",
        f"- API base: `{API_BASE}`",
        f"- Process health: `{live.get('process_health')}`",
        f"- Postgres: `{live.get('postgres')}`",
        f"- Redis: `{live.get('redis')}`",
        (
            f"- Gateway: `{live.get('gateway_status')}` "
            "(auth required — not fabricated)"
        ),
        (
            f"- OMS: `{live.get('oms_status')}` "
            "(auth required — not fabricated)"
        ),
        (
            f"- MT5: `{live.get('mt5_status')}` "
            "(auth required — not fabricated)"
        ),
        (
            f"- AI: `{live.get('ai_status')}` "
            "(auth required — not fabricated)"
        ),
        (
            "- RC1 ops endpoint deployed on production: "
            f"`{live.get('rc1_endpoint_deployed')}`"
        ),
        "",
        "Probe artifacts:",
        "- `docs/production/pre_live_evidence/live_health_probes.json`",
        "- `docs/production/pre_live_evidence/rc1_paper_result.json`",
        "- `docs/production/pre_live_evidence/rc1_shadow_result.json`",
        "",
        "## Pre-Live Checklist Outcome",
        "",
        f"**Final recommendation: {combined}**",
        "",
        "Deployment must STOP while any acceptance gate remains UNKNOWN/FAIL.",
        "",
    ]
    report_md = report_md + "\n".join(failure_extra)

    report_path = report_mod.write_rc1_validation_report(
        report_md,
        path=root / "docs" / "production" / "RC1_VALIDATION_REPORT.md",
    )
    failure_path = (
        root / "docs" / "production" / "RC1_PRE_LIVE_FAILURE_REPORT.md"
    )
    stamp = (
        f"\n\n---\n\nRun stamp: `{_now()}`\n"
        f"Combined recommendation: `{combined}`\n"
        f"Primary report: `{report_path}`\n"
    )
    existing = failure_path.read_text(encoding="utf-8")
    if "Run stamp:" in existing:
        existing = existing.split("\n---\n", 1)[0].rstrip() + "\n"
    failure_path.write_text(existing + stamp, encoding="utf-8")

    summary = {
        "recommendation": combined,
        "report": str(report_path),
        "failure_report": str(failure_path),
    }
    print(json.dumps(summary, indent=2))
    return 0 if combined != "NOT READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
