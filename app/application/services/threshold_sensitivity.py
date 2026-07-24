"""Threshold Sensitivity Report — counterfactual gate statistics only.

Post-hoc sweep of quality / confluence gates on historical replay scores.
Never mutates ITEConfig, strategy, risk, safety, OMS, or MT5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# Live baseline (display / reference only — never written back to config).
BASELINE_QUALITY_GATE = 80
BASELINE_CONFLUENCE_GATE = 80

# Requested sensitivity ladder (descending).
GATE_LADDER: tuple[int, ...] = (80, 75, 70, 65, 60)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_score_rows(rows: list[dict[str, Any]] | list[Any]) -> list[dict[str, int]]:
    """Extract {quality, confluence} ints from replay / diagnostics rows."""
    out: list[dict[str, int]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        q = _as_int(raw.get("quality"))
        c = _as_int(raw.get("confluence"))
        if q is None and isinstance(raw.get("quality"), dict):
            q = _as_int(raw["quality"].get("score"))
        if c is None and isinstance(raw.get("confluence"), dict):
            c = _as_int(raw["confluence"].get("total"))
        if c is None:
            c = _as_int(raw.get("confluence_score") or raw.get("confidence"))
        if q is None or c is None:
            continue
        out.append({"quality": q, "confluence": c})
    return out


def _execution_stats(
    rows: list[dict[str, int]],
    *,
    quality_gate: int,
    confluence_gate: int,
) -> dict[str, Any]:
    n = len(rows)
    would = sum(
        1
        for r in rows
        if r["quality"] >= quality_gate and r["confluence"] >= confluence_gate
    )
    pct = round(100.0 * would / n, 2) if n else 0.0
    return {
        "gate": None,  # filled by caller
        "quality_gate": quality_gate,
        "confluence_gate": confluence_gate,
        "evaluations": n,
        "would_execute_count": would,
        "execution_pct": pct,
    }


def sweep_quality_gates(
    rows: list[dict[str, int]],
    *,
    gates: tuple[int, ...] = GATE_LADDER,
    confluence_held: int = BASELINE_CONFLUENCE_GATE,
) -> list[dict[str, Any]]:
    """If Quality Gate = G (Confluence held at baseline) → Execution %."""
    results: list[dict[str, Any]] = []
    for g in gates:
        row = _execution_stats(
            rows, quality_gate=g, confluence_gate=confluence_held
        )
        row["gate"] = g
        row["sweep"] = "quality"
        row["held_confluence_gate"] = confluence_held
        results.append(row)
    return results


def sweep_confluence_gates(
    rows: list[dict[str, int]],
    *,
    gates: tuple[int, ...] = GATE_LADDER,
    quality_held: int = BASELINE_QUALITY_GATE,
) -> list[dict[str, Any]]:
    """If Confluence Gate = G (Quality held at baseline) → Execution %."""
    results: list[dict[str, Any]] = []
    for g in gates:
        row = _execution_stats(
            rows, quality_gate=quality_held, confluence_gate=g
        )
        row["gate"] = g
        row["sweep"] = "confluence"
        row["held_quality_gate"] = quality_held
        results.append(row)
    return results


def build_threshold_sensitivity_report(
    opportunities: list[dict[str, Any]],
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Statistics-only sensitivity report from scored historical rows."""
    rows = normalize_score_rows(opportunities)
    qualities = [r["quality"] for r in rows]
    confluences = [r["confluence"] for r in rows]
    quality_sweep = sweep_quality_gates(rows)
    confluence_sweep = sweep_confluence_gates(rows)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "advisory_only": True,
        "statistics_only": True,
        "never_modifies_strategy": True,
        "never_modifies_thresholds": True,
        "never_modifies_live_engine": True,
        "never_modifies_risk_safety_oms_mt5": True,
        "method": (
            "Counterfactual score-gate: would_execute iff "
            "quality >= quality_gate AND confluence >= confluence_gate. "
            "Scores come from unchanged historical replay pipeline; "
            "live ITEConfig gates remain 80/80."
        ),
        "baseline": {
            "quality_gate": BASELINE_QUALITY_GATE,
            "confluence_gate": BASELINE_CONFLUENCE_GATE,
        },
        "gate_ladder": list(GATE_LADDER),
        "source": source or {},
        "sample": {
            "n_scored_evaluations": len(rows),
            "average_quality": (
                round(sum(qualities) / len(qualities), 2) if qualities else None
            ),
            "average_confluence": (
                round(sum(confluences) / len(confluences), 2)
                if confluences
                else None
            ),
            "min_quality": min(qualities) if qualities else None,
            "max_quality": max(qualities) if qualities else None,
            "min_confluence": min(confluences) if confluences else None,
            "max_confluence": max(confluences) if confluences else None,
        },
        "quality_gate_sensitivity": quality_sweep,
        "confluence_gate_sensitivity": confluence_sweep,
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """Human-readable statistics-only markdown."""
    sample = report.get("sample") or {}
    baseline = report.get("baseline") or {}
    lines: list[str] = [
        "# Threshold Sensitivity Report",
        "",
        f"- Generated at: `{report.get('generated_at', '—')}`",
        "- Advisory / statistics only — **live engines and thresholds unchanged**",
        f"- Baseline gates (live): Quality **{baseline.get('quality_gate')}** · "
        f"Confluence **{baseline.get('confluence_gate')}**",
        f"- Scored evaluations: **{sample.get('n_scored_evaluations', 0)}**",
        f"- Average quality: **{sample.get('average_quality', '—')}** · "
        f"Average confluence: **{sample.get('average_confluence', '—')}**",
        "",
        "## Quality Gate Sensitivity",
        "",
        "_Confluence gate held at baseline 80._",
        "",
        "| If Quality Gate | Execution % | Would execute | Evaluations |",
        "|---:|---:|---:|---:|",
    ]
    for row in report.get("quality_gate_sensitivity") or []:
        lines.append(
            f"| {row.get('gate')} | {row.get('execution_pct')}% | "
            f"{row.get('would_execute_count')} | {row.get('evaluations')} |"
        )
    lines.extend(
        [
            "",
            "## Confluence Gate Sensitivity",
            "",
            "_Quality gate held at baseline 80._",
            "",
            "| If Confluence Gate | Execution % | Would execute | Evaluations |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("confluence_gate_sensitivity") or []:
        lines.append(
            f"| {row.get('gate')} | {row.get('execution_pct')}% | "
            f"{row.get('would_execute_count')} | {row.get('evaluations')} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            str(report.get("method") or ""),
            "",
            "This report does **not** lower thresholds, force trades, or modify "
            "strategy / risk / safety / OMS / MT5.",
            "",
        ]
    )
    return "\n".join(lines)
