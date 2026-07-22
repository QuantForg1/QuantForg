#!/usr/bin/env python3
"""XAUUSD strategy audit CLI — recommendations only; never mutates strategy.

Writes:
  docs/production/reports/strategy_audit_<ts>.json
  docs/production/STRATEGY_AUDIT_REPORT_v1.0.1.md (when --write-md)

Optional evidence JSON:
  --trades path.json --decisions path.json --signal-facts path.json
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
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def _markdown(report: dict[str, Any]) -> str:
    hr = report.get("human_review") or {}
    lines = [
        "# QuantForg v1.0.1 — XAUUSD Strategy Audit Report",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Strategy evidence audit only. No architecture, AI, Risk, Safety, "
        "or Execution Pipeline changes. Never auto-modifies production strategy.",
        "",
        "## Verdict",
        "",
        "Feature-complete ITE SMC stack is logically consistent. Live statistical "
        "power for session/regime exit quality remains limited until more tagged "
        "trades and decisions are supplied. Recommendations only.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## Component audit",
        "",
    ]
    for c in report.get("components") or []:
        lines.append(
            f"- **{c['component']}** (`{c['status']}`): {c['finding']}"
        )
        lines.append(f"  - Evidence: `{c['evidence']}`")
    sq = report.get("signal_quality")
    lines.extend(["", "## Signal quality (example / supplied facts)", ""])
    if sq:
        lines.append(f"**Signal Quality {sq['score']} / 100** (`{sq['band']}`)")
        lines.append("")
        lines.append(f"Reason: {sq['why_entry_allowed']}")
        if sq.get("filter_opportunities"):
            lines.append("")
            lines.append("Could have been filtered:")
            for f in sq["filter_opportunities"]:
                lines.append(f"- {f}")
    else:
        lines.append("_No signal facts supplied for this run._")

    lines.extend(["", "## Entry quality", ""])
    lines.append("```json")
    lines.append(json.dumps(report.get("entry_audit"), indent=2))
    lines.append("```")
    lines.extend(["", "## Exit quality", ""])
    lines.append("```json")
    lines.append(json.dumps(report.get("exit_audit"), indent=2))
    lines.append("```")
    lines.extend(["", "## No Trade quality", ""])
    lines.append("```json")
    lines.append(json.dumps(report.get("no_trade_audit"), indent=2))
    lines.append("```")
    lines.extend(["", "## Session performance (never mixed)", ""])
    lines.append("```json")
    lines.append(json.dumps(report.get("session_performance"), indent=2))
    lines.append("```")
    lines.extend(["", "## Market regime (never mixed)", ""])
    lines.append("```json")
    lines.append(json.dumps(report.get("regime_performance"), indent=2))
    lines.append("```")
    lines.extend(["", "## Recommendations (only — never auto-applied)", ""])
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    lines.extend(["", "## Human review", "", "### Strengths", ""])
    for s in hr.get("strengths") or []:
        lines.append(f"- {s}")
    lines.extend(["", "### Weaknesses", ""])
    for s in hr.get("weaknesses") or []:
        lines.append(f"- {s}")
    lines.extend(["", "### Unknowns", ""])
    for s in hr.get("unknowns") or []:
        lines.append(f"- {s}")
    lines.extend(["", "### Open questions", ""])
    for s in hr.get("open_questions") or []:
        lines.append(f"- {s}")
    lines.extend(["", "### Future replay plan", ""])
    for s in hr.get("future_replay_plan") or []:
        lines.append(f"- {s}")
    lines.extend(
        [
            "",
            "## Hard locks",
            "",
            "- never_auto_modifies_strategy: true",
            "- never_modifies_risk_safety_execution: true",
            "- never_auto_applies: true",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    from app.application.services.xauusd_strategy_audit import (
        run_xauusd_strategy_audit,
        score_xauusd_signal,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", default=None)
    parser.add_argument("--decisions", default=None)
    parser.add_argument("--signal-facts", default=None)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo-signal",
        action="store_true",
        help="Include a demo high-quality signal score (illustrative facts only)",
    )
    args = parser.parse_args()

    trades = _load(args.trades)
    decisions = _load(args.decisions)
    signal_facts = _load(args.signal_facts)
    if args.demo_signal and signal_facts is None:
        signal_facts = {
            "mtf_aligned": True,
            "bos": True,
            "choch": False,
            "liquidity_sweep": True,
            "order_block": True,
            "fair_value_gap": True,
            "session_allowed": True,
            "spread_acceptable": True,
            "volatility_acceptable": True,
        }

    if isinstance(trades, dict):
        trades = trades.get("trades") or trades.get("items") or []
    if isinstance(decisions, dict):
        decisions = (
            decisions.get("decisions") or decisions.get("items") or []
        )

    report = run_xauusd_strategy_audit(
        trades=trades if isinstance(trades, list) else None,
        decisions=decisions if isinstance(decisions, list) else None,
        signal_facts=signal_facts if isinstance(signal_facts, dict) else None,
    )
    if args.demo_signal and isinstance(signal_facts, dict):
        report["illustrative_signal_score"] = score_xauusd_signal(signal_facts)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"strategy_audit_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = ROOT / "docs" / "production" / "STRATEGY_AUDIT_REPORT_v1.0.1.md"
        md_path.write_text(_markdown(report), encoding="utf-8")
        print(f"Wrote {md_path}")

    print(json.dumps(report.get("evidence_summary"), indent=2))
    print("recommendations:")
    for r in report.get("recommendations") or []:
        print(f"  - {r}".encode("ascii", errors="replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
