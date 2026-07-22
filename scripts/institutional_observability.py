#!/usr/bin/env python3
"""Generate Institutional Observability Platform reports.

Writes docs/production/reports/iop_*.json and optional markdown.
Never modifies trading behaviour.
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


def _md(report: dict[str, Any]) -> str:
    lines = [
        "# QuantForg v1.0.1 — Institutional Observability Platform",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Monitoring and diagnostics only. Never modifies trading "
        "behaviour or prior advisory/governance labs.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## System health",
        "",
        "```json",
        json.dumps(report.get("health"), indent=2),
        "```",
        "",
        "## Latency",
        "",
        "```json",
        json.dumps(report.get("latencies"), indent=2),
        "```",
        "",
        "## Resources",
        "",
        "```json",
        json.dumps(report.get("resources"), indent=2),
        "```",
        "",
        "## Errors",
        "",
        "```json",
        json.dumps(report.get("errors"), indent=2),
        "```",
        "",
        "## Uptime",
        "",
        "```json",
        json.dumps(report.get("uptime"), indent=2),
        "```",
        "",
        "## Dependency map",
        "",
        "```json",
        json.dumps(report.get("dependency"), indent=2),
        "```",
        "",
        "## Alerts",
        "",
        "```json",
        json.dumps(report.get("alerts"), indent=2),
        "```",
        "",
        "## Reports",
        "",
        "```json",
        json.dumps(report.get("reports"), indent=2),
        "```",
        "",
        "## Recommendations (never auto-applied)",
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
    from app.application.services.institutional_observability import (
        run_observability,
        seed_demo_observability,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Include demo latency/error samples for local report generation",
    )
    args = parser.parse_args()

    report = seed_demo_observability() if args.demo else run_observability()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"iop_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = (
            ROOT
            / "docs"
            / "production"
            / "INSTITUTIONAL_OBSERVABILITY_REPORT_v1.0.1.md"
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
