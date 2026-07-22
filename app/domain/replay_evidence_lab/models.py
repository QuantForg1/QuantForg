"""Shared types for Institutional Replay & Evidence Lab (advisory only)."""

from __future__ import annotations

from typing import Any, Literal

EvidenceLane = Literal["live", "demo", "replay", "research"]

EVIDENCE_LANES: tuple[EvidenceLane, ...] = ("live", "demo", "replay", "research")

ConfidenceLevel = Literal["insufficient", "low", "medium", "high"]

DEFAULT_EVIDENCE_THRESHOLDS: dict[str, int] = {
    "min_live_closed_trades": 50,
    "min_replay_opportunities": 500,
    "min_no_trade_observations": 100,
}

HARD_LOCKS: dict[str, bool] = {
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_performance_intelligence": True,
    "never_fabricates_metrics": True,
    "counterfactual_research_only": True,
    "never_mix_evidence_lanes": True,
}


def empty_lane_inventory() -> dict[str, list[Any]]:
    return {lane: [] for lane in EVIDENCE_LANES}
