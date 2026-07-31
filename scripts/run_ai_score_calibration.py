#!/usr/bin/env python3
"""AI Score Calibration — evidence-only Quality/Confidence audit (N production cycles).

Does NOT change thresholds or weights. Does NOT auto-recalibrate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.services.score_calibration_audit import (  # noqa: E402
    CONFIDENCE_WEIGHTS,
    QUALITY_WEIGHTS,
    run_calibration_audit,
)


def _md_table(rows: list[dict], keys: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    return lines


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

    report = run_calibration_audit(cycles)
    # Slim artifact without full per-cycle dump in markdown; keep JSON complete
    out_dir = Path("/opt/cursor/artifacts/ai-score-calibration")
    out_dir.mkdir(parents=True, exist_ok=True)

    full_path = out_dir / "CALIBRATION.json"
    full_path.write_text(json.dumps(report, indent=2) + "\n")

    # Compact JSON without per-cycle (for quick review)
    compact = {k: v for k, v in report.items() if k != "per_cycle_decompositions"}
    compact["per_cycle_count"] = len(report.get("per_cycle_decompositions") or [])
    compact["per_cycle_sample"] = (report.get("per_cycle_decompositions") or [])[:5]
    (out_dir / "CALIBRATION_SUMMARY.json").write_text(
        json.dumps(compact, indent=2) + "\n"
    )

    # Contribution histograms as separate CSV-ish JSON
    hist = {
        "quality_total": report["totals"]["quality"]["histogram"],
        "confidence_total": report["totals"]["confidence"]["histogram"],
        "quality_components": {
            c["component"]: c.get("score_histogram")
            for c in report["quality_components"]
        },
        "confidence_components": {
            c["component"]: c.get("score_histogram")
            for c in report["confidence_components"]
        },
    }
    (out_dir / "HISTOGRAMS.json").write_text(json.dumps(hist, indent=2) + "\n")

    q_rows = [
        {
            "component": c["component"],
            "weight": c["weight"],
            "mean": c["score_mean"],
            "std": c["score_std"],
            "max": c["score_max"],
            "contrib_mean": c["contribution_mean"],
            "drag": c.get("avg_total_drag"),
            "below80%": c.get("frequency_below_80_pct"),
        }
        for c in report["quality_components"]
    ]
    c_rows = [
        {
            "component": c["component"],
            "weight": c["weight"],
            "mean": c["score_mean"],
            "std": c["score_std"],
            "max": c["score_max"],
            "contrib_mean": c["contribution_mean"],
            "drag": c.get("avg_total_drag"),
            "below80%": c.get("frequency_below_80_pct"),
        }
        for c in report["confidence_components"]
    ]

    md: list[str] = [
        "# AI Score Calibration Audit (N=1000)",
        "",
        "**Evidence only. Thresholds unchanged (80/80). Weights unchanged. No auto-recalibration.**",
        "",
        f"Source: `{src}`",
        "",
        "## Totals",
        "",
        f"- Quality mean: **{report['totals']['quality']['mean']}** "
        f"(σ={report['totals']['quality']['std']}, "
        f"{report['totals']['quality']['pct_below_80']}% below 80)",
        f"- Confidence mean: **{report['totals']['confidence']['mean']}** "
        f"(σ={report['totals']['confidence']['std']}, "
        f"{report['totals']['confidence']['pct_below_80']}% below 80)",
        "",
        "### Quality total histogram",
        "",
        "```json",
        json.dumps(report["totals"]["quality"]["histogram"], indent=2),
        "```",
        "",
        "### Confidence total histogram",
        "",
        "```json",
        json.dumps(report["totals"]["confidence"]["histogram"], indent=2),
        "```",
        "",
        "## Quality component decomposition",
        "",
        f"Weights: `{QUALITY_WEIGHTS}`",
        "",
    ]
    md.extend(
        _md_table(
            q_rows,
            [
                "component",
                "weight",
                "mean",
                "std",
                "max",
                "contrib_mean",
                "drag",
                "below80%",
            ],
        )
    )
    md += [
        "",
        "## Confidence component decomposition",
        "",
        f"Weights: `{CONFIDENCE_WEIGHTS}`",
        "",
    ]
    md.extend(
        _md_table(
            c_rows,
            [
                "component",
                "weight",
                "mean",
                "std",
                "max",
                "contrib_mean",
                "drag",
                "below80%",
            ],
        )
    )
    md += [
        "",
        "## Blockers ranked by average total drag",
        "",
        "### Quality",
        "",
        "```json",
        json.dumps(report["blockers_ranked"]["quality_by_avg_drag"], indent=2),
        "```",
        "",
        "### Confidence",
        "",
        "```json",
        json.dumps(report["blockers_ranked"]["confidence_by_avg_drag"], indent=2),
        "```",
        "",
        "## Max achievable under documented caps",
        "",
        "```json",
        json.dumps(report["max_achievable"], indent=2),
        "```",
        "",
        "## Findings",
        "",
    ]
    for f in report["findings"]:
        md.append(f"- **{f['id']}**: {f['detail']}")
    md += [
        "",
        "## Structural engine counterfactual (weights/thresholds unchanged)",
        "",
        "If M15 semantics MTF lock + Liquidity v2 already apply:",
        "",
        "```json",
        json.dumps(report.get("structural_engine_counterfactual"), indent=2),
        "```",
        "",
        "## Recommendations (do not auto-apply)",
        "",
    ]
    for r in report["recommendations"]:
        md.append(
            f"{r['priority']}. `{r['action']}` — {r['proposal']} "
            f"(auto_apply={r['auto_apply']}, changes_threshold={r['changes_threshold']})"
        )
    md += [
        "",
        "## Reconstruction quality",
        "",
        "```json",
        json.dumps(report["reconstruction_quality"], indent=2),
        "```",
        "",
        f"Full per-cycle decompositions: `{full_path}` "
        f"({len(report['per_cycle_decompositions'])} rows).",
        "",
    ]
    (out_dir / "CALIBRATION.md").write_text("\n".join(md) + "\n")

    # stdout: compact summary
    print(json.dumps(compact, indent=2))
    print(f"\nWrote {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
