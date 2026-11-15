"""Phase 7 — Autonomous Trading Control (product facade).

Composes Phase 4-6 intelligence, AutoTradePolicy, RiskEngine, OMS auth
preview, live-trading status, and robot readouts.

Never order_send. Never enables LIVE. Default mode OBSERVE_ONLY.
Distinct from historical Multi-account Phase 7 ops docs.
"""

from __future__ import annotations

from typing import Any

MODEL_VERSION = "phase7-autonomy-1.0.0"

DEFAULT_MODE = "OBSERVE_ONLY"

AUTONOMY_MODES: tuple[str, ...] = (
    "OBSERVE_ONLY",
    "ASSISTED",
    "CONTROLLED_AUTOMATION",
    "RESTRICTED_OR_DISABLED",
)

DECISION_OUTCOMES: tuple[str, ...] = (
    "BUY",
    "SELL",
    "HOLD",
    "NO_TRADE",
    "REJECTED",
    "WAITING_FOR_APPROVAL",
    "EXECUTION_BLOCKED",
)

AUTH_RESULTS: tuple[str, ...] = (
    "AUTHORIZED",
    "REQUIRES_APPROVAL",
    "BLOCKED",
    "EXPIRED",
    "DUPLICATE",
    "NOT_AVAILABLE",
)

APPROVAL_ACTIONS: tuple[str, ...] = (
    "Approve",
    "Reject",
    "Request Review",
    "Expire",
    "Cancel",
)

VALIDATION_STAGES: tuple[str, ...] = (
    "market_data_freshness",
    "symbol_validity",
    "strategy_authorization",
    "signal_integrity",
    "market_regime_compatibility",
    "spread_validation",
    "volatility_validation",
    "risk_reward_validation",
    "stop_loss_validation",
    "position_sizing_validation",
    "account_eligibility",
    "broker_connectivity",
    "execution_eligibility",
    "duplicate_signal_detection",
    "expiry_validation",
)

ISOLATION_FLAGS: dict[str, Any] = {
    "observe_only": True,
    "advisory_only": True,
    "human_approval_required": True,
    "never_order_send": True,
    "phase7_live_dispatch": False,
    "never_auto_deploy_live": True,
    "never_force_trade_allowed": True,
    "never_increases_risk_limits": True,
    "never_bypasses_kill_switch": True,
    "never_fabricates_metrics": True,
    "never_invents_balances": True,
    "approved_is_not_live": True,
    "authorized_is_not_live_submit": True,
    "default_mode": DEFAULT_MODE,
    "preserves_weltrade_live_path": True,
    "mutates_engines": False,
    "influences_trading": False,
}

MODULE_ROUTES: tuple[dict[str, str], ...] = (
    {
        "id": "autonomous_trading",
        "path": "/autonomous-trading",
        "label": "Autonomous Trading",
    },
    {
        "id": "autonomy_control",
        "path": "/autonomy-control",
        "label": "Autonomy Control",
    },
    {
        "id": "decision_approvals",
        "path": "/decision-approvals",
        "label": "Decision Approvals",
    },
    {
        "id": "trade_intelligence",
        "path": "/trade-intelligence",
        "label": "Trade Intelligence",
    },
)


def isolation_payload() -> dict[str, Any]:
    return {
        **ISOLATION_FLAGS,
        "model_version": MODEL_VERSION,
        "isolation": dict(ISOLATION_FLAGS),
        "order_send": False,
    }


def data_quality(
    *,
    source: str,
    as_of: str | None = None,
    stale: bool = False,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "as_of": as_of,
        "stale": stale,
        "missing_fields": list(missing_fields or []),
        "complete": not bool(missing_fields),
    }


__all__ = [
    "APPROVAL_ACTIONS",
    "AUTH_RESULTS",
    "AUTONOMY_MODES",
    "DECISION_OUTCOMES",
    "DEFAULT_MODE",
    "ISOLATION_FLAGS",
    "MODEL_VERSION",
    "MODULE_ROUTES",
    "VALIDATION_STAGES",
    "data_quality",
    "isolation_payload",
]
