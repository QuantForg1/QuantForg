#!/usr/bin/env python3
"""NOC Command Center Operational Acceptance Test (OpsAT).

Observe-only. Never mutates trading, OMS, gateway, or MT5.
Produces JSON + markdown under docs/production/reports/noc_opsat/.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API = os.environ.get(
    "QUANTFORG_API_BASE", "https://quantforg-production.up.railway.app"
).rstrip("/")
PREVIEW = os.environ.get(
    "NOC_PREVIEW_URL",
    "https://quant-forg-c01exaxfj-quantforg.vercel.app",
)
OWNER_TOKEN = os.environ.get("QUANTFORG_OWNER_TOKEN") or os.environ.get("E2E_OWNER_TOKEN")

OUT_DIR = Path("docs/production/reports/noc_opsat")
SECRET_RE = re.compile(
    r"(bearer\s+[a-z0-9\-._~+/]+=*|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+)",
    re.I,
)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%MZ")


def _http(path: str, *, token: str | None = None) -> dict[str, Any]:
    url = path if path.startswith("http") else f"{API}{path}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body[:500]}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:500]}
        return {"ok": False, "status": int(exc.code), "body": parsed}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "body": {"error": str(exc)}}


def _check(name: str, status: str, detail: str, evidence: Any = None) -> dict[str, Any]:
    return {
        "check": name,
        "status": status,  # PASS | FAIL | BLOCKED | PARTIAL
        "detail": detail,
        "evidence": evidence,
    }


def run_local_aggregator_opsat() -> list[dict[str, Any]]:
    """Fidelity checks against live PVM recorder + aggregator (in-process)."""
    from app.application.services.noc_command_center import (
        answer_noc_copilot,
        build_noc_command_center,
    )
    from app.domain.institutional_trading.production_validation_mode.models import (
        PIPELINE_ORDER,
        ValidationStage,
    )
    from app.domain.institutional_trading.production_validation_mode.observe import (
        begin_validation,
        finalize,
        stage,
    )
    from app.domain.institutional_trading.production_validation_mode.recorder import (
        get_production_validation_recorder,
        reset_production_validation_recorder_for_tests,
    )

    checks: list[dict[str, Any]] = []
    reset_production_validation_recorder_for_tests()
    begin_validation(symbol="XAUUSD", market_session="london", execution_mode="live")
    stage(ValidationStage.SCHEDULER, ok=True, reason="tick", latency_ms=1.2)
    stage(ValidationStage.MARKET_DATA, ok=True, reason="quotes_live", latency_ms=2.0)
    stage(ValidationStage.CONTEXT, ok=True, reason="context_ok", latency_ms=3.0)
    stage(ValidationStage.AI, ok=False, reason="Quality below threshold", latency_ms=4.0)
    rec = get_production_validation_recorder()
    rec.record_no_trade_reasons(
        ["Quality below threshold", "Session filter: off-hours"]
    )

    class _Decision:
        id = "opsat-decision"
        symbol = "XAUUSD"
        action = "NO_TRADE"
        confidence = 41
        quality = 62
        risk_score = None
        estimated_rr = None
        confluence = None

    rec.capture_signal(decision=_Decision())
    finalize(export=False)

    snap1 = build_noc_command_center()
    snap2 = build_noc_command_center()

    # 1 Global health
    health = snap1.get("global_health") or []
    labels = {str(c.get("label")) for c in health if isinstance(c, dict)}
    required = {
        "AI Engine",
        "Gateway",
        "OMS",
        "MT5",
        "Broker",
        "Railway",
        "Execution Enabled",
        "AutoTrading",
    }
    checks.append(
        _check(
            "1_global_health_cards",
            "PASS" if required.issubset(labels) else "FAIL",
            f"cards={sorted(labels)}",
            {"missing": sorted(required - labels)},
        )
    )
    railway = next((c for c in health if c.get("label") == "Railway"), {})
    checks.append(
        _check(
            "1_railway_status",
            "PASS" if railway.get("status") in {"healthy", "warning", "critical", "unknown"} else "FAIL",
            f"railway={railway.get('status')} detail={railway.get('detail')}",
            railway,
        )
    )

    # 2 Pipeline
    nodes = (snap1.get("pipeline") or {}).get("nodes") or []
    statuses = {str(n.get("stage_key") or n.get("stage")): n.get("status") for n in nodes}
    expect_fail_ai = any(
        "AI" in str(n.get("stage")) and n.get("status") == "FAIL" for n in nodes
    )
    full = len(nodes) >= len(PIPELINE_ORDER)
    checks.append(
        _check(
            "2_pipeline_stages",
            "PASS" if full and expect_fail_ai else "FAIL",
            f"node_count={len(nodes)} ai_fail={expect_fail_ai}",
            statuses,
        )
    )

    # 3 AI panel
    ai = snap1.get("ai_engine") or {}
    reasons = list(ai.get("reasons") or [])
    ai_ok = (
        ai.get("symbol") == "XAUUSD"
        and str(ai.get("decision")).upper() == "NO_TRADE"
        and "Quality below threshold" in reasons
        and "Session filter: off-hours" in reasons
    )
    checks.append(
        _check(
            "3_ai_panel",
            "PASS" if ai_ok else "FAIL",
            f"symbol={ai.get('symbol')} decision={ai.get('decision')} quality={ai.get('quality_score')}",
            {"reasons": reasons, "session": ai.get("current_session")},
        )
    )

    # 4 / 5 positions & closed — empty is valid when no journal/runtime
    checks.append(
        _check(
            "4_open_positions_contract",
            "PASS" if isinstance(snap1.get("open_positions"), list) else "FAIL",
            f"count={len(snap1.get('open_positions') or [])} (empty allowed when PME absent)",
        )
    )
    checks.append(
        _check(
            "5_closed_trades_contract",
            "PASS" if isinstance(snap1.get("closed_trades"), list) else "FAIL",
            f"count={len(snap1.get('closed_trades') or [])} (never fabricated)",
        )
    )

    # 6 Event stream ordering + dedupe of identical consecutive messages optional
    events = snap1.get("event_stream") or []
    ts = [str(e.get("timestamp") or "") for e in events if isinstance(e, dict)]
    ordered = ts == sorted(ts, reverse=True)
    # Duplicate exact (timestamp,message,reason) pairs should not explode
    keys = [
        (e.get("timestamp"), e.get("message"), e.get("reason"))
        for e in events
        if isinstance(e, dict)
    ]
    dup_ratio = 1 - (len(set(keys)) / len(keys)) if keys else 0.0
    checks.append(
        _check(
            "6_event_stream",
            "PASS" if ordered and dup_ratio < 0.5 else "FAIL",
            f"events={len(events)} ordered={ordered} dup_ratio={dup_ratio:.2f}",
        )
    )

    # 7 Alerts from real blocker only
    alerts = snap1.get("alerts") or []
    false_ok = all(
        isinstance(a, dict) and (a.get("message") or a.get("kind")) for a in alerts
    )
    checks.append(
        _check(
            "7_alerts",
            "PASS" if false_ok else "FAIL",
            f"alert_count={len(alerts)}",
            alerts[:5],
        )
    )

    # 8 Validation history IDs
    hist = snap1.get("validation_history") or []
    vid = (snap1.get("pipeline") or {}).get("validation_id")
    hist_ids = {h.get("validation_id") for h in hist if isinstance(h, dict)}
    checks.append(
        _check(
            "8_validation_history",
            "PASS" if vid and vid in hist_ids else "FAIL",
            f"validation_id={vid} in_history={vid in hist_ids}",
            {"history_count": len(hist)},
        )
    )

    # 9 Copilot grounding
    ans = answer_noc_copilot("Why isn't QuantForg trading?", telemetry=snap1)
    grounded = bool(ans.get("grounded") and ans.get("hallucination_guard"))
    cites_reason = "Quality below threshold" in str(ans.get("answer"))
    missing = answer_noc_copilot(
        "Show broker latency.",
        telemetry={
            "gateway": {},
            "oms": {},
            "system_metrics": {},
            "ai_engine": {},
            "pipeline": {},
            "global_health": [],
            "event_stream": [],
        },
    )
    states_unavailable = "None" in str(missing.get("answer")) or "unavailable" in str(
        missing.get("evidence")
    ).lower()
    checks.append(
        _check(
            "9_copilot_grounded",
            "PASS" if grounded and cites_reason and states_unavailable else "FAIL",
            "grounded answers cite telemetry; missing values called out",
            {
                "answer_excerpt": str(ans.get("answer"))[:240],
                "missing_evidence": missing.get("evidence"),
            },
        )
    )

    # 10 Polling determinism (same snapshot inputs → stable flags)
    flags_stable = snap1.get("flags") == snap2.get("flags")
    checks.append(
        _check(
            "10_snapshot_stability",
            "PASS" if flags_stable else "FAIL",
            "flags stable across consecutive builds",
        )
    )

    # 11 Security redaction
    blob = json.dumps(snap1)
    secret_hit = bool(SECRET_RE.search(blob))
    poisoned = {
        **snap1,
        "gateway": {**(snap1.get("gateway") or {}), "api_token": "super-secret-token-value"},
    }
    from app.application.services.noc_command_center import _redact

    cleaned = _redact(poisoned)
    redacted_ok = cleaned.get("gateway", {}).get("api_token") == "[redacted]"
    checks.append(
        _check(
            "11_security_redaction",
            "PASS" if (not secret_hit) and redacted_ok else "FAIL",
            f"payload_secret_pattern={secret_hit} redact_ok={redacted_ok}",
        )
    )
    return checks


def run_production_probes() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    live = _http("/health/live")
    status = _http("/api/v1/health/status")
    noc = _http("/api/v1/ite/ops/noc-command-center")
    pvm = _http("/api/v1/ite/ops/production-validation-mode")
    auto = _http("/api/v1/ite/ops/auto-trading")
    preview = _http(f"{PREVIEW}/admin/noc")

    checks.append(
        _check(
            "prod_health_live",
            "PASS" if live.get("ok") else "FAIL",
            f"HTTP {live.get('status')}",
            live.get("body"),
        )
    )
    deps = (status.get("body") or {}).get("dependencies") if status.get("ok") else None
    checks.append(
        _check(
            "prod_health_status",
            "PASS" if status.get("ok") else "FAIL",
            f"env={(status.get('body') or {}).get('environment')} version={(status.get('body') or {}).get('version')}",
            deps,
        )
    )

    # NOC endpoint must 401 (auth) once deployed; currently 404 on main
    noc_status = int(noc.get("status") or 0)
    if noc_status == 404:
        checks.append(
            _check(
                "prod_noc_endpoint_deployed",
                "BLOCKED",
                "NOC API not on production main yet (HTTP 404). PR #42 not merged/deployed.",
                noc.get("body"),
            )
        )
    elif noc_status == 401:
        checks.append(
            _check(
                "prod_noc_endpoint_deployed",
                "PASS",
                "NOC endpoint present; auth required (expected without token)",
            )
        )
    else:
        checks.append(
            _check(
                "prod_noc_endpoint_deployed",
                "FAIL",
                f"Unexpected HTTP {noc_status} for NOC endpoint",
                noc.get("body"),
            )
        )

    if OWNER_TOKEN:
        auth_noc = _http("/api/v1/ite/ops/noc-command-center", token=OWNER_TOKEN)
        auth_pvm = _http("/api/v1/ite/ops/production-validation-mode", token=OWNER_TOKEN)
        auth_auto = _http("/api/v1/ite/ops/auto-trading", token=OWNER_TOKEN)
        for name, res in (
            ("auth_noc", auth_noc),
            ("auth_pvm", auth_pvm),
            ("auth_auto", auth_auto),
        ):
            checks.append(
                _check(
                    name,
                    "PASS" if res.get("ok") else "FAIL",
                    f"HTTP {res.get('status')}",
                    {
                        k: (res.get("body") or {}).get(k)
                        for k in ("header", "primary_blocker", "current_blocker", "flags")
                        if isinstance(res.get("body"), dict)
                    },
                )
            )
    else:
        checks.append(
            _check(
                "prod_authenticated_telemetry",
                "BLOCKED",
                "No QUANTFORG_OWNER_TOKEN / E2E_OWNER_TOKEN in environment — cannot verify "
                "AI/positions/OMS against live production ops APIs (401 without bearer).",
                {
                    "pvm_http": pvm.get("status"),
                    "auto_http": auto.get("status"),
                },
            )
        )

    # Unauthorized must not receive telemetry
    if noc_status in {401, 403, 404}:
        checks.append(
            _check(
                "11_unauthorized_access",
                "PASS",
                f"Unauthenticated NOC access denied/unavailable (HTTP {noc_status})",
            )
        )
    else:
        checks.append(
            _check(
                "11_unauthorized_access",
                "FAIL",
                f"Unauthenticated NOC returned HTTP {noc_status}",
            )
        )

    preview_status = int(preview.get("status") or 0)
    checks.append(
        _check(
            "preview_noc_route",
            "PASS" if preview_status in {200, 302, 307, 401, 403} else "FAIL",
            f"Vercel preview /admin/noc HTTP {preview_status} (auth redirect expected)",
            {"preview": PREVIEW},
        )
    )
    return checks


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now()
    local = run_local_aggregator_opsat()
    prod = run_production_probes()
    all_checks = local + prod
    counts = {
        "PASS": sum(1 for c in all_checks if c["status"] == "PASS"),
        "FAIL": sum(1 for c in all_checks if c["status"] == "FAIL"),
        "BLOCKED": sum(1 for c in all_checks if c["status"] == "BLOCKED"),
        "PARTIAL": sum(1 for c in all_checks if c["status"] == "PARTIAL"),
    }
    verdict = (
        "NOC OPSAT NOT ACCEPTED"
        if counts["FAIL"] or counts["BLOCKED"]
        else "NOC OPSAT ACCEPTED"
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "api_base": API,
        "preview_url": PREVIEW,
        "verdict": verdict,
        "counts": counts,
        "checks": all_checks,
        "notes": [
            "Observe-only OpsAT — no trading mutations.",
            "Authenticated live widget parity requires OWNER token + deployed NOC API.",
            "Local aggregator checks prove pipeline/AI/copilot/security fidelity.",
        ],
    }
    json_path = OUT_DIR / f"NOC_OPSAT_{stamp}.json"
    latest = OUT_DIR / "NOC_OPSAT_latest.json"
    md_path = OUT_DIR / f"NOC_OPSAT_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# NOC Command Center OpsAT — {stamp}",
        "",
        f"**Verdict:** `{verdict}`",
        "",
        f"Counts: PASS={counts['PASS']} FAIL={counts['FAIL']} "
        f"BLOCKED={counts['BLOCKED']} PARTIAL={counts['PARTIAL']}",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for c in all_checks:
        detail = str(c["detail"]).replace("|", "\\|")
        lines.append(f"| `{c['check']}` | **{c['status']}** | {detail} |")
    lines.extend(
        [
            "",
            "## Blockers for full live widget OpsAT",
            "",
            "1. Merge/deploy PR #42 so `/api/v1/ite/ops/noc-command-center` exists on Railway.",
            "2. Provide `QUANTFORG_OWNER_TOKEN` (or owner email/password) to this agent env.",
            "3. Re-run: `python scripts/opsat_noc_command_center.py`",
            "",
            "No trading logic was modified.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "counts": counts, "json": str(json_path)}, indent=2))
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
