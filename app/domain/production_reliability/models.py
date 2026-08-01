"""Shared constants for Production Reliability Program."""

from __future__ import annotations

from typing import Literal

IncidentStatus = Literal[
    "open",
    "investigating",
    "mitigated",
    "resolved",
    "postmortem",
]

INCIDENT_STATUSES: tuple[IncidentStatus, ...] = (
    "open",
    "investigating",
    "mitigated",
    "resolved",
    "postmortem",
)

# Observe-only latency channels — never fabricate when unmeasured
LATENCY_CHANNELS: tuple[str, ...] = (
    "api",
    "gateway",
    "oms",
    "mt5",
    "execution",
    "database",
    "background_job",
    "queue",
)

HEALTH_TARGETS: tuple[str, ...] = (
    "gateway",
    "oms",
    "ai",
    "mt5",
    "database",
    "redis",
    "storage",
    "api",
    "frontend",
    "jobs",
)

# Default SLO targets (availability %) — used for error-budget math only
DEFAULT_SLO_AVAILABILITY = 99.9
DEFAULT_SLA_AVAILABILITY = 99.5

HARD_LOCKS: dict[str, bool] = {
    "modifies_trading": False,
    "modifies_ai": False,
    "modifies_oms": False,
    "modifies_mt5": False,
    "modifies_risk": False,
    "modifies_cop": False,
    "modifies_enterprise_business_rules": False,
    "modifies_auth": False,
    "modifies_pricing": False,
    "additive_only": True,
    "destructive_ops_forbidden": True,
    "observe_only_metrics": True,
}
