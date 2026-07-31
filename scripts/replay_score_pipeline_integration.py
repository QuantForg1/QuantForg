#!/usr/bin/env python3
"""Replay Score Pipeline Integration over last N production cycles.

Thresholds unchanged (80/80). Weights unchanged. No automatic reduction.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.services.score_pipeline_integration_replay import (  # noqa: E402
    replay_score_pipeline_integration,
)


def main() -> int:
    src = Path("/tmp/ai-decision-collector/cycles_by_trace.json")
    if not src.exists():
        alt = ROOT / "data" / "cycles_by_trace.json"
        src = alt if alt.exists() else src
    if not src.exists():
        print(json.dumps({"error": f"missing cycles: {src}"}))
        return 1

    raw = json.loads(src.read_text())
    cycles = list(raw.values()) if isinstance(raw, dict) else list(raw)
    cycles = cycles[-1000:]
    report = replay_score_pipeline_integration(cycles)

    out = Path("/opt/cursor/artifacts/score-pipeline-integration")
    out.mkdir(parents=True, exist_ok=True)
    (out / "REPLAY.json").write_text(json.dumps(report, indent=2) + "\n")

    md = [
        "# Score Pipeline Integration — Replay (N=1000)",
        "",
        "**Thresholds unchanged (80/80). Weights unchanged. No weight inflation.**",
        "",
        f"Source: `{src}`",
        "",
        "## Averages",
        "",
        "```json",
        json.dumps(report["averages"], indent=2),
        "```",
        "",
        "## Full gate / expected broker submissions",
        "",
        "```json",
        json.dumps(report["full_gate"], indent=2),
        "```",
        "",
        "## False positives / negatives",
        "",
        "```json",
        json.dumps(report["error_proxies"], indent=2),
        "```",
        "",
        "## Score distributions (after)",
        "",
        "```json",
        json.dumps(report["distributions"], indent=2),
        "```",
        "",
        "## M15 contribution",
        "",
        "```json",
        json.dumps(report["m15_contribution"], indent=2),
        "```",
        "",
    ]
    (out / "REPLAY.md").write_text("\n".join(md) + "\n")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
