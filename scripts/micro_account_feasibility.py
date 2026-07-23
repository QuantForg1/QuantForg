#!/usr/bin/env python3
"""Generate Micro Account Mode feasibility report (advisory only).

Does not modify Institutional Mode or live execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Micro Account Mode feasibility")
    parser.add_argument(
        "--atr",
        type=str,
        default="12.00",
        help="Reference ATR in price units (default 12.00)",
    )
    args = parser.parse_args()

    from app.application.services.micro_account_feasibility import (
        report_to_markdown,
        run_micro_account_feasibility,
    )

    report = run_micro_account_feasibility(atr=Decimal(args.atr))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "docs" / "production" / "reports"
    out.mkdir(parents=True, exist_ok=True)

    json_body = json.dumps(report, indent=2) + "\n"
    (out / f"micro_account_feasibility_{stamp}.json").write_text(
        json_body, encoding="utf-8"
    )
    (out / "micro_account_feasibility_latest.json").write_text(
        json_body, encoding="utf-8"
    )

    md = report_to_markdown(report)
    (out / f"micro_account_feasibility_{stamp}.md").write_text(md, encoding="utf-8")
    (out / "MICRO_ACCOUNT_MODE.md").write_text(md, encoding="utf-8")

    sys.stdout.buffer.write(md.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")
    print(f"Wrote JSON/MD under {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
