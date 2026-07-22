"""Application service — Institutional Performance Intelligence (advisory)."""

from __future__ import annotations

from typing import Any

from app.domain.performance_intelligence.dashboard import (
    build_performance_intelligence,
    build_period_report,
)


def run_performance_intelligence(
    *,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
    period: str = "monthly",
) -> dict[str, Any]:
    """Aggregate journals into IQ dashboard. Never mutates trading systems."""
    return build_performance_intelligence(
        trades=trades,
        decisions=decisions,
        journal_rows=journal_rows,
        period=period,
    )


def run_period_report(
    *,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    period: str = "monthly",
) -> dict[str, Any]:
    from app.domain.performance_intelligence.dashboard import normalize_trade_rows

    return build_period_report(
        normalize_trade_rows(trades),
        period=period,
        decisions=decisions,
    )
