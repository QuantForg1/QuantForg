"""Application wrapper — XAUUSD strategy audit (advisory only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.xauusd_strategy_audit import (
    StrategyAuditReport,
    build_strategy_audit,
    score_signal_quality,
)


def run_xauusd_strategy_audit(
    *,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    signal_facts: dict[str, Any] | None = None,
    version: str = "1.0.1",
) -> dict[str, Any]:
    """Build audit dict. Never writes ITEConfig / Risk / Safety / Execution."""
    report: StrategyAuditReport = build_strategy_audit(
        trades=trades,
        decisions=decisions,
        signal_facts=signal_facts,
        version=version,
    )
    payload = report.to_dict()
    payload["advisory_only"] = True
    payload["never_auto_applies"] = True
    return payload


def score_xauusd_signal(facts: dict[str, Any]) -> dict[str, Any]:
    """Score a single signal. Returns unavailable if facts empty."""
    scored = score_signal_quality(facts)
    if scored is None:
        return {
            "status": "unavailable",
            "message": "Signal facts not supplied",
            "never_auto_applies": True,
        }
    out = scored.to_dict()
    out["status"] = "available"
    out["never_auto_applies"] = True
    out["display"] = f"Signal Quality {scored.score} / 100"
    return out
