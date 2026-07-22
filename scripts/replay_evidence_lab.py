#!/usr/bin/env python3
"""Generate Institutional Replay & Evidence Lab reports (advisory only).

Writes docs/production/reports/replay_evidence_*.json and optional markdown.
Never modifies strategy / risk / safety / execution / Performance Intelligence.
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


def _demo_payload() -> dict[str, Any]:
    bars = [
        {
            "timestamp": "2026-07-20T08:00:00+00:00",
            "open": 2400.0,
            "high": 2405.0,
            "low": 2398.0,
            "close": 2402.0,
        },
        {
            "timestamp": "2026-07-20T08:05:00+00:00",
            "open": 2402.0,
            "high": 2410.0,
            "low": 2401.0,
            "close": 2408.0,
        },
        {
            "timestamp": "2026-07-20T08:10:00+00:00",
            "open": 2408.0,
            "high": 2412.0,
            "low": 2395.0,
            "close": 2396.0,
        },
    ]
    opportunities = [
        {
            "timestamp": "2026-07-20T08:00:00+00:00",
            "session": "london",
            "market_regime": "trend",
            "trend": "bullish",
            "bos": True,
            "liquidity_sweep": True,
            "order_block": True,
            "fair_value_gap": False,
            "choch": False,
            "confluence_score": 92,
            "decision": "BUY",
            "direction": "BUY",
            "entry": 2402.0,
            "exit": 2410.0,
            "rr": 2.0,
            "hold_time": 300,
        },
        {
            "timestamp": "2026-07-20T08:05:00+00:00",
            "session": "london",
            "market_regime": "high_volatility",
            "trend": "bullish",
            "bos": False,
            "choch": True,
            "liquidity_sweep": False,
            "order_block": False,
            "fair_value_gap": True,
            "confluence_score": 78,
            "decision": "NO_TRADE",
            "no_trade_reason": "spread too wide",
            "direction": "BUY",
            "entry": 2408.0,
            "stop_loss": 2400.0,
            "take_profit": 2420.0,
            "bars_after": [
                {"high": 2415.0, "low": 2405.0},
                {"high": 2418.0, "low": 2399.0},
            ],
        },
        {
            "timestamp": "2026-07-21T14:00:00+00:00",
            "session": "new_york",
            "market_regime": "range",
            "trend": "neutral",
            "bos": False,
            "choch": False,
            "liquidity_sweep": True,
            "order_block": True,
            "fair_value_gap": True,
            "confluence_score": 84,
            "decision": "NO_TRADE",
            "no_trade_reason": "mtf_not_aligned",
            "direction": "SELL",
            "entry": 2390.0,
            "stop_loss": 2398.0,
            "take_profit": 2375.0,
            "bars_after": [
                {"high": 2392.0, "low": 2380.0},
                {"high": 2385.0, "low": 2374.0},
            ],
        },
    ]
    return {
        "bars": bars,
        "opportunities": opportunities,
        "live": [{"net_pnl": 12, "id": "live-demo-1"}],
        "demo": [{"id": "demo-1", "note": "labeled demo lane"}],
        "research": [],
    }


def _md(report: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.0.1 — Institutional Replay & Evidence Lab",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Historical replay + segregated evidence lanes. "
        "Never fabricates metrics. Never modifies strategy, risk, safety, "
        "execution, or Performance Intelligence.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## Replay report",
        "",
        "```json",
        json.dumps(
            {
                "status": (report.get("replay") or {}).get("status"),
                "bars_loaded": (report.get("replay") or {}).get("bars_loaded"),
                "opportunities_recorded": (report.get("replay") or {}).get(
                    "opportunities_recorded"
                ),
                "opportunities": (report.get("replay") or {}).get("opportunities"),
            },
            indent=2,
        ),
        "```",
        "",
        "## Evidence coverage report",
        "",
        "```json",
        json.dumps(report.get("evidence"), indent=2),
        "```",
        "",
        "## Confidence report",
        "",
        "```json",
        json.dumps(report.get("confidence"), indent=2),
        "```",
        "",
        "## Evidence gates",
        "",
        "```json",
        json.dumps(report.get("gates"), indent=2),
        "```",
        "",
        "## Counterfactual (research only)",
        "",
        "```json",
        json.dumps(
            {
                "research_only": (report.get("counterfactual") or {}).get(
                    "research_only"
                ),
                "feeds_production_kpis": (report.get("counterfactual") or {}).get(
                    "feeds_production_kpis"
                ),
                "no_trade_count": (report.get("counterfactual") or {}).get(
                    "no_trade_count"
                ),
                "result_histogram": (report.get("counterfactual") or {}).get(
                    "result_histogram"
                ),
            },
            indent=2,
        ),
        "```",
        "",
        "## Open questions",
        "",
    ]
    for q in (report.get("reports") or {}).get("open_questions") or []:
        lines.append(f"- {q}")
    lines.extend(
        [
            "",
            "## Recommendations (never auto-applied)",
            "",
        ]
    )
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    lines.extend(
        [
            "",
            "## Hard locks",
            "",
        ]
    )
    for k, v in (report.get("hard_locks") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    from app.application.services.replay_evidence_lab import run_replay_evidence_lab

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", default=None)
    parser.add_argument("--opportunities", default=None)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Include small demo replay set for local report generation",
    )
    args = parser.parse_args()

    bars = _load(args.bars)
    opps = _load(args.opportunities)
    live: list[Any] | None = None
    demo: list[Any] | None = None
    research: list[Any] | None = None

    if isinstance(bars, dict):
        bars = bars.get("bars") or bars.get("items") or []
    if isinstance(opps, dict):
        opps = opps.get("opportunities") or opps.get("items") or []

    if args.demo and not opps:
        demo_payload = _demo_payload()
        bars = demo_payload["bars"]
        opps = demo_payload["opportunities"]
        live = demo_payload["live"]
        demo = demo_payload["demo"]
        research = demo_payload["research"]

    report = run_replay_evidence_lab(
        bars=bars if isinstance(bars, list) else None,
        opportunities=opps if isinstance(opps, list) else None,
        live_closed_trades=live,
        demo_records=demo,
        research_records=research,
    )

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"replay_evidence_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = ROOT / "docs" / "production" / "REPLAY_EVIDENCE_LAB_REPORT_v1.0.1.md"
        md_path.write_text(_md(report), encoding="utf-8")
        print(f"Wrote {md_path}")

    print(json.dumps(report.get("evidence_summary"), indent=2))
    print("confidence:")
    print(
        json.dumps(
            {
                "overall": (report.get("confidence") or {}).get("overall_confidence"),
                "lane_samples": (report.get("confidence") or {}).get("lane_samples"),
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
