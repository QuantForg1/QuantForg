"""Read-only overview builders for Phase 5 Control Center modules."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_ops_control import (
    MODULE_ROUTES,
    PHASE5_LIFECYCLE_STAGES,
    isolation_payload,
    live_deploy_allowed,
    map_islm_stage,
)


def _safe_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return {"error": type(exc).__name__, "detail": str(exc)[:240]}


def build_hub_summary() -> dict[str, Any]:
    return {
        "ok": True,
        "modules": list(MODULE_ROUTES),
        "lifecycle_stages": list(PHASE5_LIFECYCLE_STAGES),
        "robot_controls": {
            "start": "POST /trading/robot/start",
            "pause": "POST /trading/robot/pause",
            "stop": "POST /trading/robot/stop",
            "resume": "POST /trading/robot/start (after pause)",
            "platform_live": "/live-trading/* (designated owner)",
        },
        **isolation_payload(),
    }


def build_operations_overview() -> dict[str, Any]:
    from app.application.services import quantforg_autonomous_operations as aoc

    dashboard = _safe_call(aoc.build_aoc_dashboard)
    scores = _safe_call(aoc.aoc_scores)
    queue = _safe_call(aoc.aoc_queue)
    return {
        "ok": True,
        "module": "operations",
        "aoc": dashboard if isinstance(dashboard, dict) else {"raw": dashboard},
        "scores": scores if isinstance(scores, dict) else {},
        "work_queue": (
            (queue or {}).get("work_queue") if isinstance(queue, dict) else []
        ),
        "controls": {
            "robot": ["start", "pause", "stop"],
            "resume_equals_start": True,
            "requires_backend_confirmation": True,
            "platform_live_deep_link": "/admin/live-trading",
            "aoc_mutations": False,
        },
        "module_links": list(MODULE_ROUTES),
        **isolation_payload(),
    }


def build_strategy_lifecycle_overview() -> dict[str, Any]:
    from app.application.services import (
        institutional_release_deployment as irdp,
        institutional_strategy_lifecycle as islm,
    )

    registry = _safe_call(islm.islm_registry, limit=100)
    alerts = _safe_call(islm.islm_alerts)
    irdp_dash = _safe_call(irdp.build_irdp_dashboard)

    rows_in = []
    if isinstance(registry, dict):
        rows_in = list(registry.get("registry") or [])

    mapped: list[dict[str, Any]] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        islm_stage = str(row.get("lifecycle_state") or row.get("stage") or "Draft")
        stage = map_islm_stage(islm_stage)
        human_approved = bool(row.get("human_approved") or row.get("approved"))
        risk_cleared = bool(row.get("risk_cleared") or row.get("risk_ok"))
        owner_authorized = bool(
            row.get("owner_authorized") or row.get("owner_approved")
        )
        mapped.append(
            {
                "strategy_id": row.get("strategy_id") or row.get("id"),
                "name": row.get("name") or row.get("strategy_name"),
                "islm_stage": islm_stage,
                "phase5_stage": stage,
                "version": row.get("version"),
                "human_approved": human_approved,
                "risk_cleared": risk_cleared,
                "owner_authorized": owner_authorized,
                "live_deploy_allowed": live_deploy_allowed(
                    stage=stage,
                    human_approved=human_approved,
                    risk_cleared=risk_cleared,
                    owner_authorized=owner_authorized,
                ),
                "backtest_pass_is_not_live": True,
            }
        )

    pending_approvals: list[dict[str, Any]] = []
    if isinstance(irdp_dash, dict):
        for key in ("approvals", "pending_approvals", "approval_queue"):
            val = irdp_dash.get(key)
            if isinstance(val, list):
                pending_approvals.extend([x for x in val if isinstance(x, dict)])

    return {
        "ok": True,
        "module": "strategy_lifecycle",
        "stages": list(PHASE5_LIFECYCLE_STAGES),
        "strategies": mapped,
        "strategy_count": len(mapped),
        "alerts": (alerts or {}).get("alerts") if isinstance(alerts, dict) else [],
        "irdp": {
            "release_count": (
                len(irdp_dash.get("releases") or [])
                if isinstance(irdp_dash, dict)
                else 0
            ),
            "pending_approvals": pending_approvals[:50],
        },
        "rules": {
            "backtest_pass_not_live": True,
            "ai_recommendations_advisory": True,
            "explicit_authorization_required_for_live": True,
        },
        **isolation_payload(),
    }


def build_execution_overview(
    *,
    attempts: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Metrics from real persisted attempts/decisions only — never invents fills."""
    attempts = attempts or []
    decisions = decisions or []

    total = len(attempts)
    accepted = 0
    rejected = 0
    latencies: list[float] = []
    slippages: list[float] = []

    for row in attempts:
        if not isinstance(row, dict):
            continue
        outcome = str(
            row.get("outcome") or row.get("status") or row.get("state") or ""
        ).lower()
        if outcome in {"accepted", "filled", "success", "executed"}:
            accepted += 1
        elif outcome in {"rejected", "failed", "error", "timeout"}:
            rejected += 1
        for key in ("latency_ms", "execution_latency_ms", "round_trip_ms"):
            raw = row.get(key)
            if isinstance(raw, (int, float)):
                latencies.append(float(raw))
                break
        for key in ("slippage", "slippage_pts", "slippage_pips"):
            raw = row.get(key)
            if isinstance(raw, (int, float)):
                slippages.append(float(raw))
                break

    success_rate = (accepted / total) if total else None
    rejection_rate = (rejected / total) if total else None
    avg_latency = (sum(latencies) / len(latencies)) if latencies else None
    avg_slippage = (sum(slippages) / len(slippages)) if slippages else None

    return {
        "ok": True,
        "module": "execution_intelligence",
        "metrics": {
            "attempt_count": total,
            "decision_count": len(decisions),
            "accepted_count": accepted,
            "rejected_count": rejected,
            "success_rate": success_rate,
            "rejection_rate": rejection_rate,
            "avg_latency_ms": avg_latency,
            "avg_slippage": avg_slippage,
            "fabricated": False,
            "source": "persisted_execution_attempts",
        },
        "lifecycle_stages": [
            "signal",
            "acceptance",
            "oms",
            "dispatch",
            "broker_response",
            "mt5_result",
            "position",
            "sl_tp",
            "close",
            "rejection_timeout_retry",
        ],
        "empty": total == 0,
        "disclaimer": (
            "Metrics reflect persisted execution attempts only. "
            "Signal generation is not treated as successful execution."
        ),
        **isolation_payload(),
    }


def build_accounts_overview(
    *,
    ops_summary: dict[str, Any] | None = None,
    dispatch_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ops_summary = ops_summary or {}
    dispatch_status = dispatch_status or {}
    workers = ops_summary.get("workers") or dispatch_status.get("workers") or []
    ready = 0
    stale = 0
    if isinstance(workers, list):
        for w in workers:
            if not isinstance(w, dict):
                continue
            if w.get("ready") or w.get("status") == "ready":
                ready += 1
            if w.get("stale") or w.get("heartbeat_stale"):
                stale += 1

    live_submit = bool(
        dispatch_status.get("live_submit_allowed")
        or ops_summary.get("live_submit_allowed")
    )

    return {
        "ok": True,
        "module": "account_orchestration",
        "one_primary_account_per_user": True,
        "mt5_authoritative_for_trade_allowed": True,
        "verified_live_display_not_permission": True,
        "observe_only_production": True,
        "live_submit_allowed": live_submit,
        "workers": {
            "ready_count": ready,
            "stale_count": stale,
            "rows": workers if isinstance(workers, list) else [],
        },
        "dispatch": dispatch_status,
        "ops_summary_keys": sorted(ops_summary.keys()) if ops_summary else [],
        "banner": (
            None
            if ready > 0
            else "No ready MT5 workers — orchestration is observe-only."
        ),
        **isolation_payload(),
    }


def build_risk_overview(
    *,
    ati_alerts: list[dict[str, Any]] | None = None,
    kill_switch: dict[str, Any] | None = None,
    household_stops: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "module": "risk_automation",
        "enforcement": {
            "backend_authoritative": True,
            "ui_cannot_raise_limits": True,
            "ai_cannot_override_hard_constraints": True,
            "actions": [
                "alert",
                "block_new_execution",
                "pause_strategy",
                "pause_robot",
                "require_owner_approval_to_resume",
            ],
        },
        "ati_alerts": ati_alerts or [],
        "ati_advisory_only": True,
        "kill_switch": kill_switch or {"status": "unknown", "source": "ite_ops"},
        "household_emergency_stops": household_stops or {},
        "trader_prefs_route": "/risk-center",
        **isolation_payload(),
    }


def normalize_incident(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "incident_id": str(
            row.get("incident_id")
            or row.get("id")
            or row.get("uuid")
            or f"{source}-unknown"
        ),
        "severity": row.get("severity") or row.get("level") or "unknown",
        "affected": row.get("affected") or row.get("service") or row.get("component"),
        "first_detected": row.get("first_detected")
        or row.get("created_at")
        or row.get("opened_at"),
        "last_updated": row.get("last_updated")
        or row.get("updated_at")
        or row.get("modified_at"),
        "status": row.get("status") or "open",
        "evidence": row.get("evidence") or row.get("logs") or row.get("detail"),
        "recovery_actions": row.get("recovery_actions") or [],
        "source": source,
        "never_auto_resend_uncertain_orders": True,
    }


def build_incidents_overview(
    *,
    prp_incidents: list[dict[str, Any]] | None = None,
    ite_incidents: list[dict[str, Any]] | None = None,
    worker_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for row in prp_incidents or []:
        if isinstance(row, dict):
            normalized.append(normalize_incident(row, source="production_reliability"))
    for row in ite_incidents or []:
        if isinstance(row, dict):
            normalized.append(normalize_incident(row, source="ite_reliability"))
    for row in worker_signals or []:
        if isinstance(row, dict):
            normalized.append(normalize_incident(row, source="worker_heartbeat"))

    return {
        "ok": True,
        "module": "incident_center",
        "incidents": normalized,
        "count": len(normalized),
        "actions": [
            "acknowledge",
            "assign",
            "investigate",
            "resolve",
            "escalate",
            "retry_safe",
        ],
        "recovery_rules": {
            "idempotent": True,
            "never_auto_resend_uncertain_orders": True,
            "reconcile_with_mt5_first": True,
            "never_bypass_safety_on_restart": True,
        },
        **isolation_payload(),
    }


def build_governance_summary(
    *,
    audit_events: list[dict[str, Any]] | None = None,
    islm_approvals: list[dict[str, Any]] | None = None,
    irdp_approvals: list[dict[str, Any]] | None = None,
    qsf_approvals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    queue: list[dict[str, Any]] = []
    for source, rows in (
        ("islm", islm_approvals or []),
        ("irdp", irdp_approvals or []),
        ("qsf", qsf_approvals or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            queue.append(
                {
                    "source": source,
                    "id": row.get("id") or row.get("approval_id"),
                    "status": row.get("status") or "pending",
                    "target": row.get("target")
                    or row.get("strategy_id")
                    or row.get("release_id"),
                    "requested_at": row.get("requested_at") or row.get("created_at"),
                }
            )

    sanitized_events: list[dict[str, Any]] = []
    secret_keys = {
        "password",
        "api_key",
        "token",
        "secret",
        "credential",
        "authorization",
    }
    for ev in audit_events or []:
        if not isinstance(ev, dict):
            continue
        clean = {
            k: v
            for k, v in ev.items()
            if str(k).lower() not in secret_keys
            and not any(s in str(k).lower() for s in secret_keys)
        }
        sanitized_events.append(clean)

    return {
        "ok": True,
        "module": "governance",
        "pending_approvals": queue,
        "pending_count": len(queue),
        "audit_events": sanitized_events[:100],
        "audit_count": len(sanitized_events),
        "immutable_audit": True,
        "secrets_redacted": True,
        **isolation_payload(),
    }
