#!/usr/bin/env python3
"""Run MTF alignment diagnostic on last N production cycles (evidence only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.services.mtf_alignment_diagnostic import (  # noqa: E402
    diagnose_mtf_alignment,
    load_cycles,
    propose_improvements,
)


def main() -> None:
    candidates = [
        Path("/tmp/ai-decision-collector/cycles_by_trace.json"),
        Path("/opt/cursor/artifacts/ai-decision-rejection-analysis/collected_cycles.json"),
    ]
    cycles: list = []
    source = None
    for path in candidates:
        if path.exists():
            cycles = load_cycles(path)
            source = str(path)
            break
    if not cycles:
        print("NO_CYCLES", file=sys.stderr)
        sys.exit(2)

    cycles = cycles[-1000:]
    report = diagnose_mtf_alignment(cycles)
    report["source"] = source
    report["proposed_improvements"] = propose_improvements(report)

    out = Path("/opt/cursor/artifacts/mtf-alignment-diagnostic")
    out.mkdir(parents=True, exist_ok=True)
    (out / "DIAGNOSTIC.json").write_text(json.dumps(report, indent=2))

    # Markdown summary
    lines = [
        "# MTF Alignment Diagnostic (N={})".format(report["cycles_analyzed"]),
        "",
        "**Evidence only. Thresholds unchanged. No automatic merges.**",
        "",
        f"Source: `{source}`",
        "",
        "## Full H1+M15+M5 alignment",
        "",
        f"- Count: **{report['full_h1_m15_m5_alignment']['count']}** "
        f"({report['full_h1_m15_m5_alignment']['share_pct']}%)",
        "",
        "## Direction frequency",
        "",
        "```json",
        json.dumps(report["direction_frequency"], indent=2),
        "```",
        "",
        "## Which timeframe prevented alignment?",
        "",
        "```json",
        json.dumps(report["which_timeframe_prevented_alignment"], indent=2),
        "```",
        "",
        "## Most common conflicting combinations",
        "",
    ]
    for row in report["most_common_conflicting_combinations"][:10]:
        lines.append(
            f"- `{row['combination']}` — {row['count']} ({row['share_pct']}%) — "
            f"{row['example_path']}"
        )
    lines.extend(
        [
            "",
            "## Execution trigger frequency",
            "",
        ]
    )
    for row in report["execution_trigger_frequency"][:12]:
        lines.append(
            f"- `{row['trigger']}` — {row['count']} ({row['share_pct']}%)"
        )
    lines.extend(
        [
            "",
            "## Root-cause classification",
            "",
        ]
    )
    for row in report["root_cause_classification"]:
        lines.append(f"- **{row['cause']}** — {row['count']} ({row['share_pct']}%)")
    lines.extend(
        [
            "",
            "## Structure presence",
            "",
            "```json",
            json.dumps(report["structure_presence"], indent=2),
            "```",
            "",
            "## Averages",
            "",
            "```json",
            json.dumps(report["averages"], indent=2),
            "```",
            "",
            "## Examples",
            "",
        ]
    )
    for blocker, exs in (report.get("examples_by_blocker") or {}).items():
        lines.append(f"### Blocker: `{blocker}`")
        for ex in exs:
            lines.append(
                f"- H1={ex['H1']} · M15={ex['M15']} · M5={ex['M5']} → **{ex['outcome']}** "
                f"(trigger={ex['execution_trigger']}, cause={ex['root_cause']}, "
                f"BOS={ex.get('bos')}, CHOCH={ex.get('choch')}, "
                f"OB={ex.get('order_block')}, FVG={ex.get('fvg')})"
            )
        lines.append("")
    lines.extend(["## Proposed improvements (no threshold cuts)", ""])
    for p in report["proposed_improvements"]:
        lines.append(f"### {p['id']}: {p['title']}")
        lines.append(p["rationale"])
        lines.append(f"- Safety: {p['safety']}")
        lines.append("")

    (out / "DIAGNOSTIC.md").write_text("\n".join(lines))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
