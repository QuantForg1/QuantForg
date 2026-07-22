#!/usr/bin/env python3
"""Generate Institutional Performance Intelligence reports (advisory only).

Writes docs/production/reports/performance_iq_*.json and optional markdown.
Never modifies strategy / risk / safety / execution.
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


def _load(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _md(report: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.0.1 — Institutional Performance Intelligence",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Journals / closed-trade evidence only. Never fabricates metrics. "
        "Never modifies strategy, risk, safety, or execution.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## Performance",
        "",
        "```json",
        json.dumps(report.get("performance"), indent=2),
        "```",
        "",
        "## Sessions",
        "",
        "```json",
        json.dumps(report.get("sessions"), indent=2),
        "```",
        "",
        "## Regimes",
        "",
        "```json",
        json.dumps(report.get("regimes"), indent=2),
        "```",
        "",
        "## Signals",
        "",
        "```json",
        json.dumps(report.get("signals"), indent=2),
        "```",
        "",
        "## NO_TRADE",
        "",
        "```json",
        json.dumps(report.get("no_trade"), indent=2),
        "```",
        "",
        "## Time",
        "",
        "```json",
        json.dumps(report.get("time"), indent=2),
        "```",
        "",
        "## Period report",
        "",
        "```json",
        json.dumps(report.get("report"), indent=2),
        "```",
        "",
        "## Recommendations (never auto-applied)",
        "",
    ]
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Hard locks",
            "",
            "- never_modifies_strategy: true",
            "- never_modifies_risk_safety_execution: true",
            "- never_fabricates_metrics: true",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    from app.application.services.performance_intelligence import (
        run_performance_intelligence,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", default=None)
    parser.add_argument("--decisions", default=None)
    parser.add_argument("--period", default="monthly")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Include small demo trade set for local report generation",
    )
    args = parser.parse_args()

    trades = _load(args.trades)
    decisions = _load(args.decisions)
    if isinstance(trades, dict):
        trades = trades.get("trades") or trades.get("items") or []
    if isinstance(decisions, dict):
        decisions = decisions.get("decisions") or decisions.get("items") or []

    if args.demo and not trades:
        trades = [
            {
                "net_pnl": 25,
                "session": "london",
                "regime": "trend",
                "r_multiple": 2.1,
                "opened_at": "2026-07-20T08:00:00+00:00",
                "closed_at": "2026-07-20T09:10:00+00:00",
                "bos": True,
                "order_block": True,
                "liquidity_sweep": True,
                "confluence_score": 92,
                "exit_cause": "tp",
            },
            {
                "net_pnl": -9,
                "session": "new_york",
                "regime": "range",
                "r_multiple": -0.9,
                "opened_at": "2026-07-20T15:00:00+00:00",
                "closed_at": "2026-07-20T15:40:00+00:00",
                "choch": True,
                "fair_value_gap": True,
                "confluence_score": 82,
                "exit_cause": "sl",
            },
            {
                "net_pnl": 14,
                "session": "overlap",
                "regime": "high_volatility",
                "r_multiple": 1.4,
                "opened_at": "2026-07-21T13:00:00+00:00",
                "closed_at": "2026-07-21T14:20:00+00:00",
                "bos": True,
                "liquidity_sweep": True,
                "order_block": True,
                "confluence_score": 88,
                "exit_cause": "tp",
            },
        ]
        decisions = [
            {"decision": "NO_TRADE", "reason": "spread too wide"},
            {"decision": "NO_TRADE", "reason": "mtf_not_aligned"},
            {"decision": "WATCH", "reason": "quality below threshold"},
        ]

    report = run_performance_intelligence(
        trades=trades if isinstance(trades, list) else None,
        decisions=decisions if isinstance(decisions, list) else None,
        period=args.period,
    )

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"performance_iq_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = (
            ROOT / "docs" / "production" / "PERFORMANCE_INTELLIGENCE_REPORT_v1.0.1.md"
        )
        md_path.write_text(_md(report), encoding="utf-8")
        print(f"Wrote {md_path}")

    print(json.dumps(report.get("evidence_summary"), indent=2))
    print("recommendations:")
    for r in report.get("recommendations") or []:
        print(f"  - {r}".encode("ascii", errors="replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
