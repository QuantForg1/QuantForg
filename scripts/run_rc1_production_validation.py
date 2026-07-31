#!/usr/bin/env python3
"""Run RC1 Production Validation Pipeline and write RC1_VALIDATION_REPORT.md.

Does not modify strategy, Quality/Confidence floors, weights, or risk logic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RC1 Production Validation Pipeline")
    parser.add_argument(
        "--execution-mode",
        choices=("paper", "shadow", "live"),
        default="paper",
        help="VALIDATION_EXECUTION_MODE for this run",
    )
    parser.add_argument(
        "--report",
        default="docs/production/RC1_VALIDATION_REPORT.md",
        help="Output markdown report path",
    )
    parser.add_argument(
        "--events-json",
        default="",
        help="Optional path to JSON list of replay events",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path to write full pipeline JSON result",
    )
    args = parser.parse_args(argv)

    # Ensure repo root on path
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.domain.institutional_trading.rc1_production_validation.config import (
        set_validation_runtime_for_tests,
    )
    from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
        reset_paper_engine_for_tests,
    )
    from app.domain.institutional_trading.rc1_production_validation.pipeline import (
        run_rc1_validation_pipeline,
    )
    from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
        reset_shadow_journal_for_tests,
    )
    from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
        reset_trade_recorder_for_tests,
    )

    reset_trade_recorder_for_tests()
    reset_paper_engine_for_tests()
    reset_shadow_journal_for_tests()
    set_validation_runtime_for_tests(
        enabled=True, execution_mode=args.execution_mode
    )

    events = None
    if args.events_json:
        events = json.loads(Path(args.events_json).read_text(encoding="utf-8"))

    result = run_rc1_validation_pipeline(
        events=events,
        write_report=True,
        report_path=Path(args.report),
        use_synthetic_replay_if_empty=True,
    )

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {k: v for k, v in result.items() if k != "report_markdown"},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    print(f"recommendation={result.get('recommendation')}")
    print(f"report={result.get('report_path')}")
    print(
        "eligible={eligible} rejected={rejected}".format(
            eligible=(result.get("replay") or {}).get("eligible_trades"),
            rejected=(result.get("replay") or {}).get("rejected_trades"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
