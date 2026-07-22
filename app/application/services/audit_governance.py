"""Application service — Institutional Audit Trail & Governance."""

from __future__ import annotations

from typing import Any

from app.domain.audit_governance.change_history import get_config_change_history
from app.domain.audit_governance.reports import build_audit_governance_pack
from app.domain.audit_governance.store import get_audit_store
from app.domain.audit_governance.versions import get_trade_version_registry


def record_audit_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Append an immutable governance audit event. Never mutates trading systems."""
    return get_audit_store().append(payload)


def record_config_change(payload: dict[str, Any]) -> dict[str, Any]:
    return get_config_change_history().record(payload)


def record_trade_versions(payload: dict[str, Any]) -> dict[str, Any]:
    return get_trade_version_registry().record(payload)


def run_audit_governance(*, limit: int = 500) -> dict[str, Any]:
    return build_audit_governance_pack(
        store=get_audit_store(),
        config_history=get_config_change_history(),
        versions=get_trade_version_registry(),
        limit=limit,
    )


def seed_demo_governance() -> dict[str, Any]:
    """Load a small demo audit trail for local reports — labeled demo source."""
    store = get_audit_store()
    cfg = get_config_change_history()
    vers = get_trade_version_registry()

    demo_events = [
        {
            "timestamp": "2026-07-22T09:00:00Z",
            "category": "gateway",
            "severity": "info",
            "component": "mt5_gateway",
            "action": "gateway_connected",
            "previous_state": "disconnected",
            "new_state": "connected",
            "actor": "system",
            "source": "demo",
            "environment": "demo",
            "reason": "gateway heartbeat restored",
            "correlation_id": "corr-demo-1",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:02:00Z",
            "category": "broker",
            "severity": "info",
            "component": "mt5",
            "action": "broker_login",
            "previous_state": "logged_out",
            "new_state": "logged_in",
            "actor": "operator.alice",
            "source": "demo",
            "environment": "demo",
            "reason": "session start",
            "correlation_id": "corr-demo-1",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:05:00Z",
            "category": "operations",
            "severity": "warning",
            "component": "ops_control_plane",
            "action": "ops_promotion",
            "previous_state": "SHADOW",
            "new_state": "CANARY",
            "actor": "owner.bob",
            "source": "demo",
            "environment": "demo",
            "reason": "OWNER-approved canary promote",
            "approval": {"required": True, "granted_by": "owner.bob"},
            "correlation_id": "corr-demo-2",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:06:00Z",
            "category": "execution",
            "severity": "critical",
            "component": "execution_gate",
            "action": "execution_enabled",
            "previous_state": "false",
            "new_state": "true",
            "actor": "owner.bob",
            "source": "demo",
            "environment": "demo",
            "reason": "canary execution arm",
            "approval": {"required": True, "granted_by": "owner.bob"},
            "correlation_id": "corr-demo-2",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:07:00Z",
            "category": "strategy",
            "severity": "info",
            "component": "trade_journal",
            "action": "trade_version_tagged",
            "previous_state": None,
            "new_state": "515822",
            "actor": "system",
            "source": "demo",
            "environment": "demo",
            "reason": "permanent version stamp",
            "correlation_id": "corr-demo-3",
            "session_id": "sess-demo-1",
            "result": "recorded",
            "versions": {
                "strategy": "v1.0.1",
                "risk": "v1.0.1",
                "safety": "v1.0.1",
                "execution": "v1.0.1",
                "configuration": "v1.0.1",
            },
        },
        {
            "timestamp": "2026-07-22T09:10:00Z",
            "category": "system",
            "severity": "info",
            "component": "reporting",
            "action": "daily_report_generated",
            "previous_state": None,
            "new_state": "generated",
            "actor": "system",
            "source": "demo",
            "environment": "demo",
            "reason": "end of morning brief cycle",
            "correlation_id": "corr-demo-4",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:12:00Z",
            "category": "safety",
            "severity": "critical",
            "component": "kill_switch",
            "action": "kill_switch_armed",
            "previous_state": "disarmed",
            "new_state": "armed",
            "actor": "owner.bob",
            "source": "demo",
            "environment": "demo",
            "reason": "manual safety drill",
            "approval": {"required": True, "granted_by": "owner.bob"},
            "correlation_id": "corr-demo-5",
            "session_id": "sess-demo-1",
            "result": "success",
        },
        {
            "timestamp": "2026-07-22T09:15:00Z",
            "category": "evidence",
            "severity": "warning",
            "component": "evidence_gates",
            "action": "evidence_gates_failed",
            "previous_state": "unknown",
            "new_state": "failed",
            "actor": "system",
            "source": "demo",
            "environment": "demo",
            "reason": "insufficient live closed trades",
            "correlation_id": "corr-demo-6",
            "session_id": "sess-demo-1",
            "result": "recorded",
        },
    ]

    for ev in demo_events:
        try:
            store.append(ev)
        except ValueError:
            # Idempotent demo seed if re-run with same ids — assign fresh ids
            ev = {**ev, "event_id": None}
            # force new id by omitting — normalize generates uuid
            payload = {k: v for k, v in ev.items() if k != "event_id"}
            store.append(payload)

    cfg.record(
        {
            "timestamp": "2026-07-22T09:04:00Z",
            "scope": "execution_settings",
            "key": "EXECUTION_ENABLED",
            "previous_value": "false",
            "new_value": "true",
            "environment": "demo",
            "version": "v1.0.1",
            "actor": "owner.bob",
            "approval": "OWNER",
            "reason": "canary arm",
        }
    )
    vers.record(
        {
            "trade_id": "515822",
            "timestamp": "2026-07-22T09:07:00Z",
            "versions": {
                "strategy": "v1.0.1",
                "risk": "v1.0.1",
                "safety": "v1.0.1",
                "execution": "v1.0.1",
                "configuration": "v1.0.1",
            },
        }
    )
    return run_audit_governance()
