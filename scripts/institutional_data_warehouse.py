#!/usr/bin/env python3
"""Generate Institutional Data Warehouse reports (analytics only).

Writes docs/production/reports/idw_*.json and optional markdown.
Never modifies production trading systems.
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
        "# QuantForg v1.0.1 — Institutional Data Warehouse",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Read-only analytics warehouse. Never modifies production "
        "records or trading behaviour.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## Inventory",
        "",
        "```json",
        json.dumps(report.get("inventory"), indent=2),
        "```",
        "",
        "## Analytics",
        "",
        "```json",
        json.dumps(report.get("analytics"), indent=2),
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
    from app.application.services.institutional_data_warehouse import (
        run_warehouse,
        seed_demo_warehouse,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed demo warehouse datasets for local report generation",
    )
    args = parser.parse_args()

    report = seed_demo_warehouse() if args.demo else run_warehouse()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"idw_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = (
            ROOT
            / "docs"
            / "production"
            / "INSTITUTIONAL_DATA_WAREHOUSE_REPORT_v1.0.1.md"
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
