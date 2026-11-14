"""Application facade — Phase 5 Institutional Ops Control Center."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_ops_control import MODEL_VERSION, isolation_payload
from app.domain.institutional_ops_control.overview import (
    build_accounts_overview,
    build_execution_overview,
    build_governance_summary,
    build_hub_summary,
    build_incidents_overview,
    build_operations_overview,
    build_risk_overview,
    build_strategy_lifecycle_overview,
)


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "order_send": False,
        "auto_live_deploy": False,
        **isolation_payload(),
    }


def summary() -> dict[str, Any]:
    return build_hub_summary()


def operations_overview() -> dict[str, Any]:
    return build_operations_overview()


def strategy_lifecycle_overview() -> dict[str, Any]:
    return build_strategy_lifecycle_overview()


def execution_overview(
    *,
    attempts: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_execution_overview(attempts=attempts, decisions=decisions)


def accounts_overview(
    *,
    ops_summary: dict[str, Any] | None = None,
    dispatch_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_accounts_overview(
        ops_summary=ops_summary,
        dispatch_status=dispatch_status,
    )


def risk_overview(
    *,
    ati_alerts: list[dict[str, Any]] | None = None,
    kill_switch: dict[str, Any] | None = None,
    household_stops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_risk_overview(
        ati_alerts=ati_alerts,
        kill_switch=kill_switch,
        household_stops=household_stops,
    )


def incidents_overview(
    *,
    prp_incidents: list[dict[str, Any]] | None = None,
    ite_incidents: list[dict[str, Any]] | None = None,
    worker_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_incidents_overview(
        prp_incidents=prp_incidents,
        ite_incidents=ite_incidents,
        worker_signals=worker_signals,
    )


def governance_summary(
    *,
    audit_events: list[dict[str, Any]] | None = None,
    islm_approvals: list[dict[str, Any]] | None = None,
    irdp_approvals: list[dict[str, Any]] | None = None,
    qsf_approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_governance_summary(
        audit_events=audit_events,
        islm_approvals=islm_approvals,
        irdp_approvals=irdp_approvals,
        qsf_approvals=qsf_approvals,
    )
