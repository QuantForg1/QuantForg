"""Constants for Live Trading Evidence Program."""

from __future__ import annotations

HARD_LOCKS: dict[str, bool] = {
    "modifies_trading": False,
    "modifies_ai": False,
    "modifies_risk": False,
    "modifies_oms": False,
    "modifies_mt5": False,
    "modifies_execution_intelligence": False,
    "modifies_adaptive_intelligence": False,
    "modifies_scanner": False,
    "modifies_opportunity_ranking": False,
    "modifies_trade_queue": False,
    "modifies_cop": False,
    "modifies_enterprise": False,
    "modifies_reliability_platform": False,
    "modifies_continuous_improvement": False,
    "modifies_auth": False,
    "modifies_pricing": False,
    "forces_trades": False,
    "lowers_thresholds": False,
    "bypasses_protections": False,
    "fabricates_evidence": False,
    "additive_only": True,
    "observe_only": True,
}

# Canonical evidence field names — null when unobserved
TRADE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "trade_id",
    "decision_id",
    "symbol",
    "direction",
    "entry",
    "exit",
    "lot",
    "risk_pct",
    "quality",
    "confidence",
    "mtf",
    "liquidity",
    "volatility",
    "execution_score",
    "slippage",
    "latency",
    "session",
    "market_regime",
    "management_events",
    "close_reason",
    "pnl",
    "duration",
)
