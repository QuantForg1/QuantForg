"""Authoritative LIVE eligibility registry for QuantForg strategies.

LIVE-executable ≠ participates in analysis. Research/catalog engines may vote
advisably; only profiles listed as ``live_executable`` may become the SOE
selected OMS strategy — and only through existing Risk/OMS/MT5/owner gates.

Never auto-approves LIVE capital. Never enables grid/martingale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

EligibilityTier = Literal[
    "live_executable",
    "analysis_advisory",
    "ops_gated",
    "catalog_only",
    "forbidden",
]


@dataclass(frozen=True, slots=True)
class StrategyEligibility:
    strategy_id: str
    name: str
    tier: EligibilityTier
    participates_in_analysis: bool
    may_select_for_oms: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "tier": self.tier,
            "participates_in_analysis": self.participates_in_analysis,
            "may_select_for_oms": self.may_select_for_oms,
            "notes": self.notes,
            "live_auto_authorize": False,
        }


_REGISTRY: tuple[StrategyEligibility, ...] = (
    StrategyEligibility(
        "smc_scalping",
        "SMC Scalping",
        "live_executable",
        True,
        True,
        "SCALPING_V1 production pack — SOE selectable under Risk/OMS gates",
    ),
    StrategyEligibility(
        "trend_continuation",
        "Trend Continuation Scalping",
        "live_executable",
        True,
        True,
        "SCALPING_V1 production pack",
    ),
    StrategyEligibility(
        "breakout_scalping",
        "Breakout Scalping",
        "live_executable",
        True,
        True,
        "SCALPING_V1 production pack",
    ),
    StrategyEligibility(
        "range_mean_reversion",
        "Range Mean-Reversion Scalping",
        "live_executable",
        True,
        True,
        "SCALPING_V1 production pack — regime gated",
    ),
    StrategyEligibility(
        "momentum_scalping",
        "Momentum Scalping",
        "live_executable",
        True,
        True,
        "SCALPING_V1 production pack — min_momentum enforced",
    ),
    StrategyEligibility(
        "institutional_alpha_v5",
        "Institutional Alpha v5",
        "ops_gated",
        True,
        False,
        "Symbol ranking / desk mode — ops enable; not SOE OMS winner alone",
    ),
    StrategyEligibility(
        "m1_micro",
        "M1 Micro Setups",
        "ops_gated",
        True,
        False,
        "Unified decision arbitration; m1_live_submit opt-in",
    ),
    StrategyEligibility(
        "ite_swing_confluence",
        "ITE Swing Confluence",
        "analysis_advisory",
        True,
        False,
        "Active when trading_mode=swing — not a named OMS strategy id",
    ),
    StrategyEligibility(
        "trend_following",
        "Trend Following Plugin",
        "analysis_advisory",
        True,
        False,
        "Strategy Engine plugin — intentions only",
    ),
    StrategyEligibility(
        "ma_cross",
        "MA Cross Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; catalog profile not LIVE OMS",
    ),
    StrategyEligibility(
        "rsi",
        "RSI Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "macd",
        "MACD Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "bollinger",
        "Bollinger Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "breakout",
        "Breakout Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "momentum",
        "Momentum Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "mean_reversion",
        "Mean Reversion Plugin",
        "analysis_advisory",
        True,
        False,
        "Plugin analysis vote; not LIVE OMS",
    ),
    StrategyEligibility(
        "session_breakout",
        "Session Breakout",
        "catalog_only",
        False,
        False,
        "Catalog-only — not implemented as live OMS profile",
    ),
    StrategyEligibility(
        "alpha_factory",
        "Alpha Factory",
        "analysis_advisory",
        True,
        False,
        "Research lab — never order_send",
    ),
    StrategyEligibility(
        "scalping_ai_v2",
        "Scalping AI V2",
        "analysis_advisory",
        True,
        False,
        "Advisory hardening loop — never order_send",
    ),
    StrategyEligibility(
        "asi",
        "Adaptive Scalping Intelligence",
        "analysis_advisory",
        True,
        False,
        "Advisory coach — never auto-modify risk",
    ),
    StrategyEligibility(
        "grid",
        "Grid",
        "forbidden",
        False,
        False,
        "Hard-forbidden in live config",
    ),
    StrategyEligibility(
        "martingale",
        "Martingale",
        "forbidden",
        False,
        False,
        "Hard-forbidden in live config",
    ),
)


def list_eligibility() -> tuple[StrategyEligibility, ...]:
    return _REGISTRY


def live_executable_ids() -> tuple[str, ...]:
    return tuple(r.strategy_id for r in _REGISTRY if r.may_select_for_oms)


def analysis_participant_ids() -> tuple[str, ...]:
    return tuple(r.strategy_id for r in _REGISTRY if r.participates_in_analysis)


def eligibility_snapshot() -> dict[str, Any]:
    rows = [r.to_dict() for r in _REGISTRY]
    return {
        "strategies": rows,
        "live_executable_count": sum(1 for r in rows if r["may_select_for_oms"]),
        "analysis_participant_count": sum(
            1 for r in rows if r["participates_in_analysis"]
        ),
        "auto_authorize_live": False,
        "note": (
            "LIVE execution still requires ops LIVE mode, EXECUTION_ENABLED, "
            "Risk, OMS, MT5, and owner gates. Registry never bypasses them."
        ),
        "disclaimer": "Historical data does not guarantee future profitability.",
    }
