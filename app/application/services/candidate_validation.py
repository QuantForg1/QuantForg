"""Candidate Validation — offline A/B of production vs research candidate.

Production: Quality 80 / Confluence 80
Candidate:  Quality 70 / Confluence 75

Same 90-day walk, same spread / commission / latency assumptions.
Never modifies production thresholds or engines.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.services.threshold_performance_analysis import (
    BASELINE_CONFLUENCE,
    BASELINE_QUALITY,
    run_threshold_performance_analysis,
)
from app.domain.trading.gold_only import GOLD_SYMBOL

PRODUCTION_QUALITY = BASELINE_QUALITY  # 80
PRODUCTION_CONFLUENCE = BASELINE_CONFLUENCE  # 80
CANDIDATE_QUALITY = 70
CANDIDATE_CONFLUENCE = 75

COMPARE_KEYS: tuple[str, ...] = (
    "executed_trades",
    "win_rate",
    "profit_factor",
    "expectancy",
    "net_profit",
    "maximum_drawdown_pct",
    "recovery_factor",
    "sharpe_ratio",
    "average_rr",
)

LABELS: dict[str, str] = {
    "executed_trades": "Trades",
    "win_rate": "Win Rate",
    "profit_factor": "Profit Factor",
    "expectancy": "Expectancy",
    "net_profit": "Net Profit",
    "maximum_drawdown_pct": "Maximum Drawdown",
    "recovery_factor": "Recovery Factor",
    "sharpe_ratio": "Sharpe Ratio",
    "average_rr": "Average RR",
}


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _find_cell(
    matrix: list[dict[str, Any]], *, quality: int, confluence: int
) -> dict[str, Any] | None:
    for row in matrix:
        if int(row.get("quality_gate", -1)) == quality and int(
            row.get("confluence_gate", -1)
        ) == confluence:
            return row
    return None


def _delta(prod: float | None, cand: float | None) -> float | None:
    if prod is None or cand is None:
        return None
    return round(cand - prod, 6)


def decide_candidate(
    *,
    production: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Recommend candidate only if PF↑ AND Exp↑ AND DD not materially worse."""
    pf_p = _f(production.get("profit_factor"))
    pf_c = _f(candidate.get("profit_factor"))
    exp_p = _f(production.get("expectancy"))
    exp_c = _f(candidate.get("expectancy"))
    dd_p = _f(production.get("maximum_drawdown_pct"))
    dd_c = _f(candidate.get("maximum_drawdown_pct"))

    pf_improves = (
        pf_p is not None and pf_c is not None and pf_c > pf_p
    )
    exp_improves = (
        exp_p is not None and exp_c is not None and exp_c > exp_p
    )

    # Material DD increase: > +10% relative or +1 percentage point (whichever larger).
    dd_materially_worse = False
    dd_cap = None
    if dd_p is not None and dd_c is not None:
        dd_cap = max(dd_p * 1.10, dd_p + 1.0)
        dd_materially_worse = dd_c > dd_cap
    elif dd_c is not None and dd_p is None:
        dd_materially_worse = True

    dd_ok = not dd_materially_worse
    pass_all = bool(pf_improves and exp_improves and dd_ok)

    checks = {
        "profit_factor_improves": pf_improves,
        "expectancy_improves": exp_improves,
        "drawdown_not_materially_worse": dd_ok,
        "production_profit_factor": pf_p,
        "candidate_profit_factor": pf_c,
        "production_expectancy": exp_p,
        "candidate_expectancy": exp_c,
        "production_drawdown_pct": dd_p,
        "candidate_drawdown_pct": dd_c,
        "drawdown_accept_cap": dd_cap,
    }

    if pass_all:
        return {
            "action": "research_candidate_eligible",
            "recommend_candidate": True,
            "auto_applied": False,
            "never_modifies_production": True,
            "keep_production_until_operator_promotes": True,
            "production": {
                "quality_gate": PRODUCTION_QUALITY,
                "confluence_gate": PRODUCTION_CONFLUENCE,
            },
            "candidate": {
                "quality_gate": CANDIDATE_QUALITY,
                "confluence_gate": CANDIDATE_CONFLUENCE,
            },
            "summary": (
                f"Candidate Q{CANDIDATE_QUALITY}/C{CANDIDATE_CONFLUENCE} meets "
                "PF↑ + Expectancy↑ + non-material DD tests versus production "
                f"Q{PRODUCTION_QUALITY}/C{PRODUCTION_CONFLUENCE}. "
                "Production remains unchanged until an operator explicitly promotes."
            ),
            "checks": checks,
        }

    reasons: list[str] = []
    if not pf_improves:
        reasons.append("Profit Factor does not improve versus production.")
    if not exp_improves:
        reasons.append("Expectancy does not improve versus production.")
    if not dd_ok:
        reasons.append("Maximum Drawdown increases materially versus production.")
    reasons.append(
        f"Recommend keeping production Q{PRODUCTION_QUALITY}/C{PRODUCTION_CONFLUENCE}."
    )
    return {
        "action": "keep_production",
        "recommend_candidate": False,
        "auto_applied": False,
        "never_modifies_production": True,
        "production": {
            "quality_gate": PRODUCTION_QUALITY,
            "confluence_gate": PRODUCTION_CONFLUENCE,
        },
        "candidate": {
            "quality_gate": CANDIDATE_QUALITY,
            "confluence_gate": CANDIDATE_CONFLUENCE,
        },
        "summary": (
            f"Recommend keeping Q{PRODUCTION_QUALITY}/C{PRODUCTION_CONFLUENCE}."
        ),
        "reasons": reasons,
        "checks": checks,
    }


def build_comparison_table(
    production: dict[str, Any], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in COMPARE_KEYS:
        p = production.get(key)
        c = candidate.get(key)
        rows.append(
            {
                "metric": LABELS[key],
                "key": key,
                "production": p,
                "candidate": c,
                "delta": _delta(_f(p), _f(c)),
            }
        )
    return rows


async def run_candidate_validation(
    *,
    days: int = 90,
    max_evaluations: int = 120,
    equity: Decimal = Decimal("10000"),
) -> dict[str, Any]:
    """Replay production and candidate on identical 90-day walk. Research only."""
    # Restrict matrix to the two gate pairs of interest (plus shared axes for engine).
    # Engine builds full cartesian product of provided gate lists — pass only needed
    # unique Q and C values, then select the two cells.
    report = await run_threshold_performance_analysis(
        days=days,
        max_evaluations=max_evaluations,
        equity=equity,
        quality_gates=(PRODUCTION_QUALITY, CANDIDATE_QUALITY),
        confluence_gates=(PRODUCTION_CONFLUENCE, CANDIDATE_CONFLUENCE),
    )
    matrix = list(report.get("matrix") or [])
    production = _find_cell(
        matrix, quality=PRODUCTION_QUALITY, confluence=PRODUCTION_CONFLUENCE
    )
    candidate = _find_cell(
        matrix, quality=CANDIDATE_QUALITY, confluence=CANDIDATE_CONFLUENCE
    )
    if production is None or candidate is None:
        return {
            "schema_version": "1.0.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "unavailable",
            "symbol": GOLD_SYMBOL,
            "research_only": True,
            "never_modifies_production": True,
            "message": "Could not resolve production and/or candidate cells.",
            "decision": {
                "action": "keep_production",
                "recommend_candidate": False,
                "summary": (
                    f"Recommend keeping Q{PRODUCTION_QUALITY}/C{PRODUCTION_CONFLUENCE}."
                ),
            },
        }

    decision = decide_candidate(production=production, candidate=candidate)
    comparison = build_comparison_table(production, candidate)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "available",
        "symbol": GOLD_SYMBOL,
        "research_only": True,
        "offline_only": True,
        "advisory_only": True,
        "never_modifies_production": True,
        "never_modifies_strategy": True,
        "never_modifies_risk_safety_oms_mt5": True,
        "same_replay": {
            "days": days,
            "max_evaluations": max_evaluations,
            "evaluations": report.get("evaluations"),
            "spread_model": "fixed_0.30_points",
            "commission_model": "none_explicit_embedded_in_R_pnl",
            "latency_model": "identical_walk_clock_shared_bars",
            "slippage_model": "half_spread_research",
        },
        "production": {
            "label": "Current Production",
            "quality_gate": PRODUCTION_QUALITY,
            "confluence_gate": PRODUCTION_CONFLUENCE,
            "metrics": {k: production.get(k) for k in COMPARE_KEYS},
            "cell": production,
        },
        "candidate": {
            "label": "Candidate",
            "quality_gate": CANDIDATE_QUALITY,
            "confluence_gate": CANDIDATE_CONFLUENCE,
            "metrics": {k: candidate.get(k) for k in COMPARE_KEYS},
            "cell": candidate,
        },
        "comparison": comparison,
        "decision": decision,
        "source_evaluations": report.get("evaluations"),
        "elapsed_ms": report.get("elapsed_ms"),
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    prod = report.get("production") or {}
    cand = report.get("candidate") or {}
    decision = report.get("decision") or {}
    lines = [
        "# Candidate Validation Report",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Symbol: `{report.get('symbol')}`",
        "- Offline research only — **production never modified**",
        f"- Evaluations: **{report.get('source_evaluations')}**",
        "",
        "## Configurations",
        "",
        f"- **Current Production:** Quality **{prod.get('quality_gate')}** / "
        f"Confluence **{prod.get('confluence_gate')}**",
        f"- **Candidate:** Quality **{cand.get('quality_gate')}** / "
        f"Confluence **{cand.get('confluence_gate')}**",
        "",
        "## Comparison",
        "",
        "| Metric | Production 80/80 | Candidate 70/75 | Delta |",
        "|---|---:|---:|---:|",
    ]
    for row in report.get("comparison") or []:
        lines.append(
            f"| {row.get('metric')} | {row.get('production')} | "
            f"{row.get('candidate')} | {row.get('delta')} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            decision.get("summary", "Recommend keeping 80 / 80."),
            "",
        ]
    )
    for reason in decision.get("reasons") or []:
        lines.append(f"- {reason}")
    checks = decision.get("checks") or {}
    if checks:
        lines.extend(
            [
                "",
                "### Gate checks",
                "",
                f"- Profit Factor improves: **{checks.get('profit_factor_improves')}**",
                f"- Expectancy improves: **{checks.get('expectancy_improves')}**",
                f"- Drawdown not materially worse: "
                f"**{checks.get('drawdown_not_materially_worse')}**",
                "",
            ]
        )
    lines.append("Production thresholds remain Q80/C80. This report never applies changes.")
    lines.append("")
    return "\n".join(lines)


def comparison_to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["metric", "key", "production", "candidate", "delta"],
    )
    writer.writeheader()
    for row in report.get("comparison") or []:
        writer.writerow(row)
    return buf.getvalue()


def build_pdf_bytes(report: dict[str, Any]) -> bytes:
    """Minimal PDF 1.4 from the markdown report — no external deps."""
    md = report_to_markdown(report)
    lines: list[str] = []
    for raw in md.splitlines():
        line = raw.replace("**", "").replace("`", "").replace("#", "").strip()
        if line:
            lines.append(line[:110])
        if len(lines) >= 55:
            break
    if not lines:
        lines = ["Candidate Validation", "No data"]

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    y = 780
    content = ["BT", "/F1 9 Tf", "12 TL"]
    for line in lines:
        content.append(f"1 0 0 1 40 {y} Tm ({esc(line)}) Tj")
        y -= 12
        if y < 40:
            break
    content.append("ET")
    stream = "\n".join(content)
    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
        f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream endobj",
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1", errors="replace")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1", errors="replace"))
    pdf += f"xref\n0 {len(objects) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for i in range(1, len(offsets)):
        pdf += f"{offsets[i]:010d} 00000 n \n"
    pdf += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    pdf += f"startxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", errors="replace")
