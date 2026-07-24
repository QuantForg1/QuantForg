#!/usr/bin/env python3
"""Run historical replay → Threshold Sensitivity Report (statistics only).

Never modifies live strategy, thresholds, risk, safety, OMS, or MT5.
Writes docs/production/reports/threshold_sensitivity_*.json (+ .md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def _run_replay(*, days: int, max_evaluations: int) -> dict[str, Any]:
    from app.application.services.production_replay_validation import (
        run_production_replay,
    )

    return await run_production_replay(
        days=days,
        max_evaluations=max_evaluations,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Threshold Sensitivity Report (advisory statistics only)"
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-evaluations", type=int, default=120)
    parser.add_argument(
        "--opportunities",
        type=str,
        default=None,
        help="Optional JSON file with opportunities (skip live replay run)",
    )
    parser.add_argument("--write-md", action="store_true", default=True)
    parser.add_argument("--no-md", action="store_true")
    args = parser.parse_args()

    from app.application.services.threshold_sensitivity import (
        build_threshold_sensitivity_report,
        report_to_markdown,
    )

    if args.opportunities:
        payload = json.loads(Path(args.opportunities).read_text(encoding="utf-8"))
        if isinstance(payload, list):
            opportunities = payload
            source = {"kind": "opportunities_file", "path": args.opportunities}
        else:
            opportunities = list(payload.get("opportunities") or [])
            source = {
                "kind": "replay_report_file",
                "path": args.opportunities,
                "replay_generated_at": payload.get("generated_at"),
                "params": payload.get("params"),
            }
    else:
        replay = asyncio.run(
            _run_replay(days=args.days, max_evaluations=args.max_evaluations)
        )
        opportunities = list(replay.get("opportunities") or [])
        source = {
            "kind": "production_replay",
            "simulation_only": True,
            "order_send_called": False,
            "days": args.days,
            "max_evaluations": args.max_evaluations,
            "replay_generated_at": replay.get("generated_at"),
            "eligible_bars_considered": replay.get("eligible_bars_considered"),
            "n_opportunities": len(opportunities),
        }

    report = build_threshold_sensitivity_report(opportunities, source=source)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "docs" / "production" / "reports"
    json_path = out_dir / f"threshold_sensitivity_{stamp}.json"
    latest_json = out_dir / "threshold_sensitivity_latest.json"
    md_path = out_dir / f"threshold_sensitivity_{stamp}.md"
    latest_md = out_dir / "THRESHOLD_SENSITIVITY_REPORT.md"

    body = json.dumps(report, indent=2, sort_keys=False)
    _write(json_path, body + "\n")
    _write(latest_json, body + "\n")

    write_md = args.write_md and not args.no_md
    if write_md:
        md = report_to_markdown(report)
        _write(md_path, md)
        _write(latest_md, md)

    # Console summary (report only)
    print(report_to_markdown(report))
    print(f"Wrote {json_path}")
    if write_md:
        print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
