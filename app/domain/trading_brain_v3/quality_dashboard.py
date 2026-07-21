"""Continuous Quality Dashboard — aggregates supplied quality metrics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.types import BrainInput, ModuleResult


def build_quality_dashboard(
    inp: BrainInput,
    config: TradingBrainConfig,
    *,
    module_scores: dict[str, Decimal | None],
) -> ModuleResult:
    reasons: list[str] = []
    details: dict[str, Any] = {"panels": []}
    metrics = inp.quality_metrics

    panels: list[dict[str, Any]] = []
    for name, score in module_scores.items():
        panels.append(
            {
                "panel_id": name,
                "title": name.replace("_", " ").title(),
                "status": "available" if score is not None else "unavailable",
                "score": str(score) if score is not None else None,
            }
        )

    if isinstance(metrics, dict) and metrics:
        for key, value in list(metrics.items())[:20]:
            panels.append(
                {
                    "panel_id": f"metric_{key}",
                    "title": str(key),
                    "status": "available",
                    "value": value if not isinstance(value, (dict, list)) else None,
                    "note": "Operator-supplied metric",
                }
            )
        reasons.append(f"{len(metrics)} quality metrics supplied")
    else:
        reasons.append("No extra quality_metrics — dashboard uses module scores only")

    available_scores = [s for s in module_scores.values() if s is not None]
    if not available_scores and not metrics:
        return ModuleResult(
            module="continuous_quality_dashboard",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="Await data",
            reasons=(
                "No quality inputs — never fabricates dashboard metrics",
            ),
            details={"panels": panels},
        )

    if available_scores:
        avg = (
            sum(available_scores) / Decimal(len(available_scores))
        ).quantize(Decimal("0.01"))
    else:
        avg = Decimal("50")

    details["panels"] = panels
    details["min_discipline_score"] = str(config.min_discipline_score)
    reasons.append(f"Composite module quality {avg}")
    reasons.append("Dashboard is observational — not a profitability claim")
    return ModuleResult(
        module="continuous_quality_dashboard",
        status="available",
        score=avg,
        passed=avg >= Decimal("50"),
        recommendation="Monitor",
        reasons=tuple(reasons),
        details=details,
    )
