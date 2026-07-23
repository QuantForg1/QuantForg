#!/usr/bin/env python3
"""Offline Threshold Performance Analysis (Research).

Runs independent Q×C gate replays on XAUUSD. Never modifies live thresholds
or engines. Writes JSON, CSV, PDF, and markdown under docs/production/reports/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Threshold Performance Analysis (offline research only)"
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--max-evaluations", type=int, default=120)
    args = parser.parse_args()

    from app.application.services.threshold_performance_analysis import (
        build_pdf_bytes,
        matrix_to_csv,
        report_to_markdown,
        run_threshold_performance_analysis,
    )

    report = asyncio.run(
        run_threshold_performance_analysis(
            days=args.days,
            max_evaluations=args.max_evaluations,
        )
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "docs" / "production" / "reports"
    out.mkdir(parents=True, exist_ok=True)

    json_body = json.dumps(report, indent=2) + "\n"
    (out / f"threshold_performance_{stamp}.json").write_text(json_body, encoding="utf-8")
    (out / "threshold_performance_latest.json").write_text(json_body, encoding="utf-8")

    csv_body = matrix_to_csv(report)
    (out / f"threshold_performance_{stamp}.csv").write_text(csv_body, encoding="utf-8")
    (out / "threshold_performance_latest.csv").write_text(csv_body, encoding="utf-8")

    md = report_to_markdown(report)
    (out / f"threshold_performance_{stamp}.md").write_text(md, encoding="utf-8")
    (out / "THRESHOLD_PERFORMANCE_ANALYSIS.md").write_text(md, encoding="utf-8")

    pdf = build_pdf_bytes(report)
    (out / f"threshold_performance_{stamp}.pdf").write_bytes(pdf)
    (out / "threshold_performance_latest.pdf").write_bytes(pdf)

    # Avoid Windows console encoding issues
    sys.stdout.buffer.write(md.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    print(f"Wrote JSON/CSV/PDF/MD under {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
