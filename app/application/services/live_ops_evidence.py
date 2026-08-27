"""Read-only live operations evidence — never mutates OMS/risk/safety/broker.

Authenticated OWNER/ADMIN GET only. No order_send, no credential values,
no JWT persistence. Reuses the existing Bearer session (qf_access_token).
"""

from __future__ import annotations

from typing import Any

from app.application.services.launch_readiness import build_launch_readiness
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)

_FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "secret",
        "mt5_gateway_token",
        "mt5_gateway_caller_token",
    }
)


def _scrub(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            str(k): _scrub(v)
            for k, v in payload.items()
            if str(k).lower() not in _FORBIDDEN_KEYS
        }
    if isinstance(payload, list):
        return [_scrub(v) for v in payload]
    return payload


def build_live_ops_evidence(
    plane: OperationsControlPlane,
    *,
    settings: Settings,
) -> dict[str, Any]:
    """Observe-only snapshot for operator evidence / control-center reads."""
    readiness = build_launch_readiness(
        plane, settings=settings, owner_authorized=True
    )
    components: dict[str, Any] = {}
    try:
        from app.application.services.production_component_health import (
            collect_trading_component_health,
        )

        components = collect_trading_component_health(settings)
    except Exception as exc:
        logger.info(
            "live_ops_evidence_components_failed",
            error=type(exc).__name__,
        )
        components = {
            "error": type(exc).__name__,
            "statuses": {},
        }

    phase_a: dict[str, Any] = {}
    try:
        from app.domain.institutional_trading.phase_a.plane import get_phase_a_plane

        phase_a = get_phase_a_plane().snapshot()
    except Exception:
        phase_a = {"phase": "A", "unavailable": True}

    payload = {
        "read_only": True,
        "oms_authority": False,
        "mt5_order_authority": False,
        "mutations_allowed": False,
        "never_submits_orders": True,
        "never_modifies_risk": True,
        "never_modifies_phase_a": True,
        "never_modifies_broker_credentials": True,
        "auth": {
            "mechanism": "bearer",
            "session_key": "qf_access_token",
            "roles": ["owner", "admin"],
            "scope": "evidence_observability",
        },
        "first_blocking_lock": readiness.first_blocking_lock,
        "remaining_locks": list(readiness.remaining_locks),
        "execution_block_code": readiness.execution_block_code,
        "execution_state": readiness.execution_state,
        "launch_locks": [i.to_dict() for i in readiness.items],
        "trading_components": {
            "statuses": components.get("statuses") or {},
            "timing": components.get("timing") or {},
            "all_ready_for_limited_pilot": bool(
                components.get("all_ready_for_limited_pilot")
            ),
        },
        "phase_a": {
            "kill_switch": phase_a.get("kill_switch"),
            "burst_latch": phase_a.get("burst_latch"),
            "reject_burst": (
                (phase_a.get("burst_latch") or {}).get("reject_burst")
                if isinstance(phase_a.get("burst_latch"), dict)
                else None
            ),
            "reconciliation": phase_a.get("reconciliation"),
        },
        "verification": readiness.verification,
    }
    try:
        from app.domain.institutional_trading.ai_scalping.live_health import (
            get_live_health_monitor,
        )

        live_health = get_live_health_monitor().snapshot()
        payload["live_health"] = {
            "allow_new_entries": live_health.get("allow_new_entries"),
            "block_reason": live_health.get("block_reason"),
            "symbol_rejects": live_health.get("symbol_rejects"),
            "reject_burst": live_health.get("reject_burst"),
            "reject_burst_count": live_health.get("reject_burst_count"),
            "reject_burst_window_seconds": live_health.get(
                "reject_burst_window_seconds"
            ),
            "last_execution_reject": live_health.get("last_execution_reject"),
            "health": live_health.get("health"),
        }
    except Exception:
        payload["live_health"] = {"unavailable": True}

    scanner: dict[str, Any] = {}
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None and hasattr(runtime, "status"):
            st = runtime.status()
            scanner = {
                "scanner_running": st.get("scanner_running"),
                "last_cycle_timestamp": st.get("last_cycle_timestamp"),
                "cycle_age_seconds": st.get("cycle_age_seconds"),
                "last_successful_cycle": st.get("last_successful_cycle"),
                "last_failure": st.get("last_failure"),
                "restart_count": st.get("restart_count"),
                "restart_reason": st.get("restart_reason"),
                "scheduler_stalled": st.get("scheduler_stalled"),
                "new_entries_blocked_for_recovery": st.get(
                    "new_entries_blocked_for_recovery"
                ),
            }
    except Exception:
        scanner = {"unavailable": True}
    payload["scanner"] = scanner

    try:
        from app.domain.institutional_trading.operations.infrastructure_heartbeats import (
            CLOUDFLARED_HEARTBEAT,
            GATEWAY_HEARTBEAT,
            MT5_HEARTBEAT,
            heartbeat_snapshot,
            note_heartbeat,
        )

        statuses = (components.get("statuses") or {}) if isinstance(components, dict) else {}
        gw = statuses.get("gateway") or {}
        mt5 = statuses.get("mt5") or {}
        gw_ok = str(gw.get("status") or "").upper() == "HEALTHY"
        mt5_ok = str(mt5.get("status") or "").upper() in {"CONNECTED", "HEALTHY"}
        note_heartbeat(
            GATEWAY_HEARTBEAT,
            ok=gw_ok,
            state=str(gw.get("status") or "UNKNOWN"),
            reason=None if gw_ok else str(gw.get("detail") or "gateway_down"),
        )
        note_heartbeat(
            MT5_HEARTBEAT,
            ok=mt5_ok,
            state=str(mt5.get("status") or "UNKNOWN"),
            reason=None if mt5_ok else str(mt5.get("detail") or "mt5_disconnected"),
        )
        tunnel_up = bool(
            ((gw.get("evidence") or {}) if isinstance(gw, dict) else {}).get(
                "cloudflare_tunnel_up"
            )
        )
        note_heartbeat(
            CLOUDFLARED_HEARTBEAT,
            ok=tunnel_up,
            state="UP" if tunnel_up else "DOWN",
            reason=None if tunnel_up else "cloudflare_tunnel_down",
        )
        payload["heartbeats"] = heartbeat_snapshot()
    except Exception:
        payload["heartbeats"] = {"unavailable": True}

    try:
        from app.domain.institutional_trading.operations.resource_snapshot import (
            collect_resource_snapshot,
        )

        payload["resources"] = collect_resource_snapshot()
    except Exception:
        payload["resources"] = {"unavailable": True}

    try:
        from app.infrastructure.brokers.mt5.deployment_topology import topology_snapshot

        payload["topology"] = topology_snapshot()
    except Exception:
        payload["topology"] = {"unavailable": True}

    payload["should_blind_retry_order_submit"] = False
    payload["take_is_not_executed"] = True
    payload["executed_requires_real_ticket"] = True

    cleaned = _scrub(payload)
    return cleaned if isinstance(cleaned, dict) else payload
