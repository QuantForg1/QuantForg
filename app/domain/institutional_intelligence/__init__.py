"""Phase 6 — Institutional Intelligence (advisory product facade).

Composes ATI / Phase 5 ops / IRAP / QPM / execution / QDIE / reports.
Never order_send. Never auto-rebalance LIVE. Never increases risk limits.
Never presents forecasts as guaranteed outcomes.
"""

from __future__ import annotations

from typing import Any

MODEL_VERSION = "phase6-intel-1.0.0"

ISOLATION_FLAGS: dict[str, Any] = {
    "observe_only": True,
    "advisory_only": True,
    "human_approval_required": True,
    "never_order_send": True,
    "never_auto_deploy_live": True,
    "never_auto_rebalance": True,
    "never_increases_risk_limits": True,
    "never_guarantees_forecasts": True,
    "never_bypasses_kill_switch": True,
    "never_fabricates_metrics": True,
    "never_invents_balances": True,
    "approved_is_not_live": True,
    "preserves_weltrade_live_path": True,
    "mutates_engines": False,
    "influences_trading": False,
}

RECOMMENDATION_STATUSES: tuple[str, ...] = (
    "Proposed",
    "Under Review",
    "Approved",
    "Rejected",
    "Expired",
    "Applied",
)

MODULE_ROUTES: tuple[dict[str, str], ...] = (
    {
        "id": "intelligence_center",
        "path": "/intelligence-center",
        "label": "Intelligence Center",
    },
    {
        "id": "predictive_market",
        "path": "/predictive-market-intelligence",
        "label": "Predictive Market",
    },
    {
        "id": "strategy_analytics",
        "path": "/strategy-analytics",
        "label": "Strategy Analytics",
    },
    {
        "id": "predictive_risk",
        "path": "/predictive-risk",
        "label": "Predictive Risk",
    },
    {
        "id": "portfolio_optimization",
        "path": "/portfolio-optimization",
        "label": "Portfolio Optimization",
    },
    {
        "id": "execution_optimization",
        "path": "/execution-optimization",
        "label": "Execution Optimization",
    },
    {
        "id": "decision_intelligence",
        "path": "/decision-intelligence",
        "label": "Decision Intelligence",
    },
    {
        "id": "institutional_reports",
        "path": "/institutional-reports",
        "label": "Institutional Reports",
    },
)


def isolation_payload() -> dict[str, Any]:
    return {
        **ISOLATION_FLAGS,
        "model_version": MODEL_VERSION,
        "isolation": dict(ISOLATION_FLAGS),
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
    "ISOLATION_FLAGS",
    "MODEL_VERSION",
    "MODULE_ROUTES",
    "RECOMMENDATION_STATUSES",
    "data_quality",
    "isolation_payload",
]
