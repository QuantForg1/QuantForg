"""Research Lab — PDF-ready research report assembly (structured JSON)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_research_report(
    *,
    strategy: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    regime: dict[str, Any] | None,
    review: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    promotion: dict[str, Any] | None,
    recommendations: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble a print/PDF-ready research document from real research outputs."""
    name = (strategy or {}).get("name") or (strategy or {}).get("key") or "Strategy"
    return {
        "status": "available",
        "format": "pdf_ready_json",
        "generated_at": datetime.now(UTC).isoformat(),
        "title": f"Research Report — {name}",
        "sections": {
            "strategy": strategy or {},
            "performance": metrics or {},
            "risk": {
                "max_drawdown_pct": (metrics or {}).get("max_drawdown_pct"),
                "sortino_ratio": (metrics or {}).get("sortino_ratio"),
                "sharpe_ratio": (metrics or {}).get("sharpe_ratio"),
            },
            "market_regime": regime or {},
            "ai_review": review or {},
            "validation": validation or {},
            "promotion": promotion or {},
            "recommendations": recommendations
            or [
                "Keep Decision Engine as final gatekeeper",
                "Prefer walk-forward stability before promotion eligibility",
                "Do not interpret research as a profit guarantee",
            ],
            "charts": {
                "equity_curve_ref": "attach from validation.backtest.equity_curve",
                "monte_carlo_ref": "attach from validation.monte_carlo.confidence",
                "note": (
                    "Chart series supplied by UI from validation payloads "
                    "— not fabricated"
                ),
            },
        },
        "disclaimer": (
            "Research Lab is analysis only. Never submits trades. "
            "Never bypasses EXECUTION_ENABLED. No profit promises."
        ),
        "advisory_only": True,
        "autonomous_trading": False,
    }
