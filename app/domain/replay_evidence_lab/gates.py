"""Evidence gates — advisory thresholds before strategy-change recommendations."""

from __future__ import annotations

from typing import Any

from app.domain.replay_evidence_lab.models import DEFAULT_EVIDENCE_THRESHOLDS


def merge_thresholds(overrides: dict[str, Any] | None) -> dict[str, int]:
    merged = dict(DEFAULT_EVIDENCE_THRESHOLDS)
    for key, raw in (overrides or {}).items():
        if key not in merged:
            continue
        try:
            merged[key] = max(0, int(raw))
        except (TypeError, ValueError):
            continue
    return merged


def evaluate_evidence_gates(
    *,
    live_closed_trades: int,
    replay_opportunities: int,
    no_trade_observations: int,
    thresholds: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Do not recommend strategy changes unless thresholds are met.

    Gates are configurable and advisory only. Never auto-modify strategy.
    """
    th = merge_thresholds(thresholds)
    checks = [
        {
            "id": "live_closed_trades",
            "label": "Live closed trades",
            "observed": int(live_closed_trades),
            "required": th["min_live_closed_trades"],
            "passed": live_closed_trades >= th["min_live_closed_trades"],
        },
        {
            "id": "replay_opportunities",
            "label": "Replay opportunities",
            "observed": int(replay_opportunities),
            "required": th["min_replay_opportunities"],
            "passed": replay_opportunities >= th["min_replay_opportunities"],
        },
        {
            "id": "no_trade_observations",
            "label": "NO_TRADE observations",
            "observed": int(no_trade_observations),
            "required": th["min_no_trade_observations"],
            "passed": no_trade_observations >= th["min_no_trade_observations"],
        },
    ]
    all_passed = all(bool(c["passed"]) for c in checks)
    return {
        "status": "available",
        "thresholds": th,
        "checks": checks,
        "all_passed": all_passed,
        "may_recommend_strategy_changes": all_passed,
        "advisory_only": True,
        "never_auto_modifies_strategy": True,
        "note": (
            "Strategy-change recommendations remain blocked until all evidence "
            "gates pass — gates are advisory and never mutate production"
        ),
    }
