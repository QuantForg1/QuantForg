#!/usr/bin/env python3
"""Generate Institutional Trading Operations Center reports (advisory only).

Writes docs/production/reports/trading_operations_center_*.json and optional MD.
Never modifies strategy / risk / safety / execution / Performance IQ / Evidence Lab.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _demo() -> dict[str, Any]:
    return {
        "ops_facts": {
            "trading_date": "2026-07-22",
            "gateway_connected": True,
            "broker_connected": True,
            "mt5_logged_in": True,
            "market_open": True,
            "xauusd_ready": True,
            "risk_ready": True,
            "safety_ready": True,
            "execution_enabled": False,
            "ops_mode": "SHADOW",
            "market_regime": "trend",
            "volatility_expectation": "normal",
        },
        "expected_sessions": ["london", "new_york", "overlap"],
        "calendar_available": True,
        "high_impact_news": [
            {"title": "US CPI", "impact": "high", "time": "12:30Z"},
        ],
        "trades": [
            {
                "net_pnl": 25,
                "session": "london",
                "r_multiple": 2.1,
                "opened_at": "2026-07-22T08:00:00+00:00",
                "closed_at": "2026-07-22T09:10:00+00:00",
            },
            {
                "net_pnl": -9,
                "session": "new_york",
                "r_multiple": -0.9,
                "opened_at": "2026-07-22T15:00:00+00:00",
                "closed_at": "2026-07-22T15:40:00+00:00",
            },
            {
                "net_pnl": 14,
                "session": "overlap",
                "r_multiple": 1.4,
                "opened_at": "2026-07-22T13:00:00+00:00",
                "closed_at": "2026-07-22T14:20:00+00:00",
            },
        ],
        "previous_week_trades": [
            {
                "net_pnl": 8,
                "session": "london",
                "r_multiple": 1.0,
                "opened_at": "2026-07-15T08:00:00+00:00",
                "closed_at": "2026-07-15T09:00:00+00:00",
            },
            {
                "net_pnl": -12,
                "session": "new_york",
                "r_multiple": -1.2,
                "opened_at": "2026-07-15T15:00:00+00:00",
                "closed_at": "2026-07-15T15:50:00+00:00",
            },
        ],
        "decisions": [
            {"decision": "NO_TRADE", "reason": "spread too wide"},
            {"decision": "NO_TRADE", "reason": "spread too wide"},
            {"decision": "NO_TRADE", "reason": "mtf_not_aligned"},
        ],
        "evidence_pack": {
            "evidence_summary": {
                "live_records": 3,
                "demo_records": 1,
                "replay_opportunities": 12,
                "research_records": 2,
                "no_trade_observations": 3,
                "overall_confidence": "insufficient",
                "gates_passed": False,
            },
            "confidence": {
                "overall_confidence": "insufficient",
                "lane_samples": {
                    "live_closed_trades": {
                        "sample_size": 3,
                        "confidence": "insufficient",
                        "coverage": 0.06,
                    },
                    "replay_opportunities": {
                        "sample_size": 12,
                        "confidence": "insufficient",
                        "coverage": 0.024,
                    },
                    "no_trade_observations": {
                        "sample_size": 3,
                        "confidence": "insufficient",
                        "coverage": 0.03,
                    },
                },
            },
        },
    }


def _md(report: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.0.1 — Institutional Trading Operations Center",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Ops brief, checklist, EOD/weekly/monthly reviews, alerts. "
        "Never fabricates metrics. Never modifies strategy, risk, safety, "
        "execution, Performance IQ, or Evidence Lab.",
        "",
        "## Operational summary",
        "",
        "```json",
        json.dumps(
            {
                "checklist": {
                    "all_passed": (report.get("checklist") or {}).get("all_passed"),
                    "passed": (report.get("checklist") or {}).get("passed_count"),
                    "total": (report.get("checklist") or {}).get("total"),
                    "failures": (report.get("checklist") or {}).get("failures"),
                },
                "alerts": (report.get("operational_alerts") or {}).get("alert_count"),
                "executive": report.get("executive_dashboard"),
            },
            indent=2,
        ),
        "```",
        "",
        "## Daily brief",
        "",
        "```json",
        json.dumps(report.get("daily_brief"), indent=2),
        "```",
        "",
        "## Checklist",
        "",
        "```json",
        json.dumps(report.get("checklist"), indent=2),
        "```",
        "",
        "## End-of-day",
        "",
        "```json",
        json.dumps(report.get("end_of_day"), indent=2),
        "```",
        "",
        "## Weekly review",
        "",
        "```json",
        json.dumps(report.get("weekly_review"), indent=2),
        "```",
        "",
        "## Monthly review",
        "",
        "```json",
        json.dumps(report.get("monthly_review"), indent=2),
        "```",
        "",
        "## Operational alerts",
        "",
        "```json",
        json.dumps(report.get("operational_alerts"), indent=2),
        "```",
        "",
        "## Recommendations (ops only — never strategy changes)",
        "",
    ]
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    lines.extend(["", "## Hard locks", ""])
    for k, v in (report.get("hard_locks") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    from app.application.services.trading_operations_center import (
        run_trading_operations_center,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", default=None)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    payload: dict[str, Any] = {}
    if args.payload:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    if args.demo and not payload:
        payload = _demo()

    report = run_trading_operations_center(
        ops_facts=payload.get("ops_facts"),
        expected_sessions=payload.get("expected_sessions"),
        high_impact_news=payload.get("high_impact_news"),
        calendar_available=payload.get("calendar_available"),
        trades=payload.get("trades"),
        decisions=payload.get("decisions"),
        previous_week_trades=payload.get("previous_week_trades"),
        evidence_pack=payload.get("evidence_pack"),
        performance_pack=payload.get("performance_pack"),
        execution_quality=payload.get("execution_quality"),
    )

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"trading_operations_center_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = (
            ROOT / "docs" / "production" / "TRADING_OPERATIONS_CENTER_REPORT_v1.0.1.md"
        )
        md_path.write_text(_md(report), encoding="utf-8")
        print(f"Wrote {md_path}")

    exec_dash = report.get("executive_dashboard") or {}
    print(
        json.dumps(
            {
                "ops_all_passed": (exec_dash.get("operations_status") or {}).get(
                    "all_passed"
                ),
                "alerts": (report.get("operational_alerts") or {}).get("alert_count"),
                "confidence": (exec_dash.get("confidence") or {}).get("overall"),
            },
            indent=2,
        )
    )
    print("recommendations:")
    for r in report.get("recommendations") or []:
        print(f"  - {r}".encode("ascii", errors="replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
