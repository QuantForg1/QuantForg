"""Shared constants — Institutional Trading Operations Center (advisory)."""

from __future__ import annotations

from typing import Any

HARD_LOCKS: dict[str, bool] = {
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_performance_intelligence": True,
    "never_modifies_replay_evidence_lab": True,
    "never_fabricates_metrics": True,
    "recommendations_only": True,
    "never_suggests_strategy_changes": True,
}

# Operator resolution copy for ITOC checklist (ops actions only).
CHECKLIST_RESOLVE: dict[str, str] = {
    "gateway_connected": (
        "Restore Windows MT5 Gateway + Cloudflare tunnel; "
        "confirm gateway /health and Railway MT5_GATEWAY_BASE_URL"
    ),
    "broker_connected": (
        "Attach/login MT5 via Broker desk; confirm broker_connected on "
        "GET /ite/ops/auto-trading"
    ),
    "mt5_logged_in": (
        "Complete MT5 login on the gateway host; renew expired session "
        "from Broker workspace"
    ),
    "market_open": (
        "Wait for market open / live XAUUSD ticks; confirm market_data_live "
        "on Auto Trading status"
    ),
    "xauusd_ready": (
        "Ensure XAUUSD is selectable and tradable on the attached MT5 account"
    ),
    "risk_ready": (
        "Clear RISK_LOCK / daily loss locks; confirm plane.daily_loss_exceeded "
        "is false"
    ),
    "safety_ready": (
        "Clear SAFETY_LOCK by disarming kill switch "
        "(POST /ite/ops/kill-switch/disarm)"
    ),
    "execution_enabled": (
        "Set Railway EXECUTION_ENABLED=true; confirm MT5_GATEWAY_BASE_URL; "
        "redeploy API (no HTTP route can flip this flag)"
    ),
    "ops_live": (
        "Promote Ops mode SHADOW → CANARY → LIVE via "
        "POST /ite/ops/launch-readiness/promote "
        "(Demo Certification is optional — not required for LIVE)"
    ),
    "evidence_healthy": (
        "Ingest live closed trades and replay opportunities into Evidence Lab; "
        "raise confidence above insufficient before treating KPIs as stable"
    ),
}

CHECKLIST_ORDER: tuple[str, ...] = (
    "gateway_connected",
    "broker_connected",
    "mt5_logged_in",
    "market_open",
    "xauusd_ready",
    "risk_ready",
    "safety_ready",
    "execution_enabled",
    "ops_live",
    "evidence_healthy",
)

CHECKLIST_LABELS: dict[str, str] = {
    "gateway_connected": "Gateway Connected",
    "broker_connected": "Broker Connected",
    "mt5_logged_in": "MT5 Logged In",
    "market_open": "Market Open",
    "xauusd_ready": "XAUUSD Ready",
    "risk_ready": "Risk Ready",
    "safety_ready": "Safety Ready",
    "execution_enabled": "Execution Enabled",
    "ops_live": "Ops LIVE",
    "evidence_healthy": "Evidence Healthy",
}


def empty_ops_facts() -> dict[str, Any]:
    return {
        "gateway_connected": None,
        "broker_connected": None,
        "mt5_logged_in": None,
        "market_open": None,
        "xauusd_ready": None,
        "risk_ready": None,
        "safety_ready": None,
        "execution_enabled": None,
        "ops_mode": None,
        "evidence_healthy": None,
        "market_regime": None,
        "volatility_expectation": None,
        "trading_date": None,
    }
