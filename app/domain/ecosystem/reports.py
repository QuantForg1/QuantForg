"""Report Center — assemble period reports from real ecosystem + paper sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_period_report(
    *,
    period: str,
    journal_stats: dict[str, Any],
    paper: dict[str, Any] | None,
    coach: dict[str, Any] | None,
    preferences: dict[str, Any] | None = None,
    performance: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
    reliability: dict[str, Any] | None = None,
    known_issues: list[str] | None = None,
    recommendations: list[str] | None = None,
) -> dict[str, Any]:
    """PDF-ready structured report — never fabricates PnL."""
    allowed = {"daily", "weekly", "monthly", "quarterly"}
    period_key = period if period in allowed else "weekly"
    default_recs = [
        "Keep Decision Engine as gatekeeper",
        "Prefer paper until Research Lab eligibility + stability",
        "Do not treat reports as profit guarantees",
        "Acknowledge grouped critical alerts before enabling Auto Trading",
    ]
    return {
        "status": "available",
        "format": "pdf_ready_json",
        "period": period_key,
        "generated_at": datetime.now(UTC).isoformat(),
        "title": f"QuantForg {period_key.title()} Report",
        "sections": {
            "performance": performance
            or journal_stats
            or {"status": "unavailable"},
            "risk": risk or {"status": "unavailable"},
            "execution": execution or {"status": "unavailable"},
            "reliability": reliability or {"status": "unavailable"},
            "journal": journal_stats,
            "paper": paper or {"status": "unavailable"},
            "coach": coach or {"status": "unavailable"},
            "known_issues": known_issues
            or [
                "Missing fields remain unavailable — never invented",
                "Wall-clock multi-day soak evidence is operator-owned",
            ],
            "preferences_snapshot": {
                "timezone": (preferences or {}).get("timezone"),
                "theme": (preferences or {}).get("theme"),
            },
            "recommendations": recommendations or default_recs,
        },
        "disclaimer": (
            "Ecosystem reports are advisory. Never auto-submit trades. "
            "Never bypass Decision Engine or EXECUTION_ENABLED."
        ),
        "advisory_only": True,
        "autonomous_trading": False,
    }
