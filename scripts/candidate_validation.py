#!/usr/bin/env python3
"""Offline Candidate Validation: Production 80/80 vs Candidate 70/75.

Never modifies production. Writes docs/production/reports/candidate_validation_*.
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
    parser = argparse.ArgumentParser(description="Candidate Validation (research only)")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--max-evaluations", type=int, default=120)
    args = parser.parse_args()

    from app.application.services.candidate_validation import (
        build_pdf_bytes,
        comparison_to_csv,
        report_to_markdown,
        run_candidate_validation,
    )

    report = asyncio.run(
        run_candidate_validation(days=args.days, max_evaluations=args.max_evaluations)
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "docs" / "production" / "reports"
    out.mkdir(parents=True, exist_ok=True)

    body = json.dumps(report, indent=2) + "\n"
    (out / f"candidate_validation_{stamp}.json").write_text(body, encoding="utf-8")
    (out / "candidate_validation_latest.json").write_text(body, encoding="utf-8")

    csv_body = comparison_to_csv(report)
    (out / f"candidate_validation_{stamp}.csv").write_text(csv_body, encoding="utf-8")
    (out / "candidate_validation_latest.csv").write_text(csv_body, encoding="utf-8")

    md = report_to_markdown(report)
    (out / f"candidate_validation_{stamp}.md").write_text(md, encoding="utf-8")
    (out / "CANDIDATE_VALIDATION_REPORT.md").write_text(md, encoding="utf-8")

    pdf = build_pdf_bytes(report)
    (out / f"candidate_validation_{stamp}.pdf").write_bytes(pdf)
    (out / "candidate_validation_latest.pdf").write_bytes(pdf)

    sys.stdout.buffer.write(md.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    print(f"Wrote reports under {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
