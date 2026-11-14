"""Phase 5 — Institutional Ops Control Center (read-mostly product facade).

Aggregates existing AOC / ISLM / IRDP / execution / multi-account / risk /
incident / audit surfaces. Never order_send. Never auto LIVE deploy.
Never weakens kill-switches or invents broker permissions.
"""

from __future__ import annotations

from typing import Any

MODEL_VERSION = "phase5-ops-1.0.0"

ISOLATION_FLAGS: dict[str, Any] = {
    "observe_only": True,
    "advisory_only": True,
    "human_approval_required": True,
    "never_order_send": True,
    "never_auto_deploy_live": True,
    "never_increases_risk_limits": True,
    "never_bypasses_kill_switch": True,
    "never_fabricates_trade_allowed": True,
    "never_auto_resends_uncertain_orders": True,
    "never_replaces_mt5_host": True,
    "preserves_weltrade_live_path": True,
    "mutates_engines": False,
    "influences_trading": False,
}

# Product-facing Phase 5 stages (governance labels; not broker LIVE).
PHASE5_LIFECYCLE_STAGES: tuple[str, ...] = (
    "Draft",
    "Backtesting",
    "Validation",
    "Risk Review",
    "Approval",
    "Deployment",
    "Monitoring",
    "Paused",
    "Rollback",
    "Archived",
)

# Map ISLM internal states → Phase 5 product stages.
ISLM_TO_PHASE5: dict[str, str] = {
    "Draft": "Draft",
    "Research": "Backtesting",
    "Replay Validation": "Validation",
    "Simulation Validation": "Validation",
    "Continuous Validation": "Validation",
    "Risk Review": "Risk Review",
    "Release Approval": "Approval",
    "Production": "Deployment",
    "Monitoring": "Monitoring",
    "Suspended": "Paused",
    "Retired": "Archived",
}

MODULE_ROUTES: tuple[dict[str, str], ...] = (
    {
        "id": "operations",
        "path": "/operations",
        "label": "Operations Center",
    },
    {
        "id": "strategy_lifecycle",
        "path": "/strategy-lifecycle",
        "label": "Strategy Lifecycle",
    },
    {
        "id": "execution_intelligence",
        "path": "/execution-intelligence",
        "label": "Execution Intelligence",
    },
    {
        "id": "account_orchestration",
        "path": "/account-orchestration",
        "label": "Account Orchestration",
    },
    {
        "id": "risk_automation",
        "path": "/risk-automation",
        "label": "Risk Automation",
    },
    {
        "id": "incident_center",
        "path": "/incident-center",
        "label": "Incident Center",
    },
    {
        "id": "governance",
        "path": "/governance",
        "label": "Governance",
    },
)


def isolation_payload() -> dict[str, Any]:
    return {
        **ISOLATION_FLAGS,
        "model_version": MODEL_VERSION,
        "isolation": dict(ISOLATION_FLAGS),
    }


def map_islm_stage(raw: str | None) -> str:
    if not raw:
        return "Draft"
    return ISLM_TO_PHASE5.get(raw, raw if raw in PHASE5_LIFECYCLE_STAGES else "Draft")


def live_deploy_allowed(
    *,
    stage: str,
    human_approved: bool,
    risk_cleared: bool,
    owner_authorized: bool,
) -> bool:
    """LIVE broker deploy requires explicit gates — backtest alone is insufficient."""
    if stage not in {"Deployment", "Monitoring"}:
        return False
    return bool(human_approved and risk_cleared and owner_authorized)


__all__ = [
    "ISLM_TO_PHASE5",
    "ISOLATION_FLAGS",
    "MODEL_VERSION",
    "MODULE_ROUTES",
    "PHASE5_LIFECYCLE_STAGES",
    "isolation_payload",
    "live_deploy_allowed",
    "map_islm_stage",
]
