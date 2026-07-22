"""Application service — Institutional Trading Operations Center."""

from __future__ import annotations

from typing import Any

from app.domain.trading_operations_center.dashboard import (
    build_trading_operations_center,
)


def run_trading_operations_center(
    *,
    ops_facts: dict[str, Any] | None = None,
    expected_sessions: list[str] | None = None,
    high_impact_news: list[dict[str, Any]] | None = None,
    calendar_available: bool | None = None,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
    previous_week_trades: list[dict[str, Any]] | None = None,
    evidence_pack: dict[str, Any] | None = None,
    performance_pack: dict[str, Any] | None = None,
    execution_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ITOC pack. Never mutates trading systems or sibling labs."""
    return build_trading_operations_center(
        ops_facts=ops_facts,
        expected_sessions=expected_sessions,
        high_impact_news=high_impact_news,
        calendar_available=calendar_available,
        trades=trades,
        decisions=decisions,
        journal_rows=journal_rows,
        previous_week_trades=previous_week_trades,
        evidence_pack=evidence_pack,
        performance_pack=performance_pack,
        execution_quality=execution_quality,
    )
