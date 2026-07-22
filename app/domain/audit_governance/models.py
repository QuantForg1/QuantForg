"""Institutional Audit Trail & Governance — models (governance only)."""

from __future__ import annotations

from typing import Literal

EventCategory = Literal[
    "operations",
    "execution",
    "risk",
    "safety",
    "strategy",
    "replay",
    "performance",
    "evidence",
    "configuration",
    "gateway",
    "broker",
    "security",
    "system",
]

EVENT_CATEGORIES: tuple[EventCategory, ...] = (
    "operations",
    "execution",
    "risk",
    "safety",
    "strategy",
    "replay",
    "performance",
    "evidence",
    "configuration",
    "gateway",
    "broker",
    "security",
    "system",
)

Severity = Literal["info", "warning", "critical"]

SEVERITIES: tuple[Severity, ...] = ("info", "warning", "critical")

HARD_LOCKS: dict[str, bool] = {
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_performance_intelligence": True,
    "never_modifies_replay_evidence_lab": True,
    "never_modifies_trading_operations_center": True,
    "append_only": True,
    "immutable_records": True,
    "never_silently_deleted": True,
    "never_silently_modified": True,
    "governance_only": True,
}

# Canonical action names for institutional ops accountability
CANONICAL_ACTIONS: tuple[str, ...] = (
    "ops_promotion",
    "execution_enabled",
    "execution_disabled",
    "kill_switch_armed",
    "kill_switch_disarmed",
    "emergency_stop",
    "gateway_connected",
    "gateway_disconnected",
    "broker_login",
    "broker_logout",
    "mt5_session_changed",
    "strategy_version_activated",
    "configuration_updated",
    "evidence_gates_passed",
    "evidence_gates_failed",
    "replay_started",
    "replay_finished",
    "daily_report_generated",
    "monthly_report_generated",
    "trade_version_tagged",
)
