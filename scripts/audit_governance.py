#!/usr/bin/env python3
"""Generate Institutional Audit Trail & Governance reports.

Writes docs/production/reports/audit_governance_*.json and optional markdown.
Never modifies strategy / risk / safety / execution / Performance IQ /
Evidence Lab / Trading Operations Center.
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
        "# QuantForg v1.0.1 — Institutional Audit Trail & Governance",
        "",
        f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "**Scope:** Governance only. Append-only immutable audit trail. "
        "Never modifies trading behaviour, strategy, risk, safety, execution, "
        "Performance IQ, Evidence Lab, or Trading Operations Center.",
        "",
        "## Evidence summary",
        "",
        "```json",
        json.dumps(report.get("evidence_summary"), indent=2),
        "```",
        "",
        "## Security",
        "",
        "```json",
        json.dumps(report.get("security"), indent=2),
        "```",
        "",
        "## Dashboard counts",
        "",
        "```json",
        json.dumps((report.get("dashboard") or {}).get("counts"), indent=2),
        "```",
        "",
        "## Forensic timeline",
        "",
        "```json",
        json.dumps(report.get("timeline"), indent=2),
        "```",
        "",
        "## Operator accountability",
        "",
        "```json",
        json.dumps(report.get("accountability"), indent=2),
        "```",
        "",
        "## Reports",
        "",
        "```json",
        json.dumps(
            {
                k: {
                    "report": (v or {}).get("report"),
                    "event_count": (v or {}).get("event_count")
                    or (v or {}).get("count"),
                }
                for k, v in (report.get("reports") or {}).items()
            },
            indent=2,
        ),
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
    from app.application.services.audit_governance import (
        run_audit_governance,
        seed_demo_governance,
    )
    from app.domain.audit_governance.change_history import get_config_change_history
    from app.domain.audit_governance.store import get_audit_store
    from app.domain.audit_governance.versions import get_trade_version_registry

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed demo governance events for local report generation",
    )
    args = parser.parse_args()

    if args.demo:
        # Isolate demo from process pollution in CLI runs
        get_audit_store().clear_for_tests_only()
        get_config_change_history().clear_for_tests_only()
        get_trade_version_registry().clear_for_tests_only()
        report = seed_demo_governance()
    else:
        report = run_audit_governance()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"audit_governance_{ts}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")

    if args.write_md:
        md_path = (
            ROOT / "docs" / "production" / "AUDIT_GOVERNANCE_REPORT_v1.0.1.md"
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
